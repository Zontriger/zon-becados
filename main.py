import sys
import re
import sqlite3
import json
import os
import pandas as pd
import unicodedata
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QGroupBox, QFileDialog, QMessageBox, QTableView,
    QAbstractItemView, QHeaderView, QDialog, QLineEdit, QComboBox,
    QFormLayout, QDialogButtonBox, QLabel, QMenu
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction, QIcon
from PySide6.QtCore import Qt, Signal

# --- Dependencia Adicional para PDF ---
try:
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    PDF_DISPONIBLE = True
except ImportError:
    PDF_DISPONIBLE = False

# --- Constantes ---
CARRERAS = [
    "Ingeniería de Sistemas", "Ingeniería de Telecomunicaciones",
    "Ingeniería Eléctrica", "Contaduría", "Administración de Desastres"
]
SEMESTRES = {
    "CINU": 0, "1": 1, "2": 2, "3": 3, "4": 4,
    "5": 5, "6": 6, "7": 7, "8": 8
}
ARCHIVO_BD = 'estudiantes.db'
ENCABEZADOS_VISUALIZACION = ["T. Cédula", "Cédula", "Nombres", "Apellidos", "Carrera", "Semestre"]
ENCABEZADOS_REQUERIDOS = set(ENCABEZADOS_VISUALIZACION)

# --- Funciones de Ayuda ---
def normalizar_texto(texto):
    """Convierte a minúsculas y elimina tildes/diacríticos para búsqueda insensible."""
    texto_normalizado = unicodedata.normalize('NFD', str(texto).lower())
    return "".join(c for c in texto_normalizado if unicodedata.category(c) != 'Mn')

# --- Lógica de la Base de Datos ---
def inicializar_bd():
    """Inicializa la base de datos y crea las tablas si no existen."""
    try:
        conexion = sqlite3.connect(ARCHIVO_BD)
        cursor = conexion.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS becados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_cedula TEXT NOT NULL CHECK(tipo_cedula IN ('V', 'E', 'P')),
                cedula INTEGER NOT NULL UNIQUE,
                nombres TEXT NOT NULL,
                apellidos TEXT NOT NULL,
                carrera TEXT NOT NULL,
                semestre INTEGER NOT NULL CHECK(semestre BETWEEN 0 AND 8)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inscritos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datos_fila TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inscritos_encabezados (
                id INTEGER PRIMARY KEY,
                encabezados TEXT NOT NULL
            )
        ''')
        conexion.commit()
        conexion.close()
    except sqlite3.Error as e:
        mostrar_error_critico("Error de Base de Datos", f"No se pudo inicializar la base de datos: {e}")
        sys.exit(1)

# --- Diálogo para Ver Información del Estudiante ---
class DialogoVerEstudiante(QDialog):
    """Diálogo para mostrar la información completa de un estudiante (solo lectura)."""
    def __init__(self, parent=None, datos_estudiante=None):
        super().__init__(parent)
        self.setWindowTitle("Información del Estudiante")
        layout = QFormLayout(self)
        mapa_etiquetas = {
            'T. Cédula': 'T. Cédula:', 'Cédula': 'Cédula:',
            'Nombres': 'Nombres:', 'Apellidos': 'Apellidos:',
            'Carrera': 'Carrera:', 'Semestre': 'Semestre:'
        }
        for clave, etiqueta in mapa_etiquetas.items():
            valor = datos_estudiante.get(clave, 'N/A')
            layout.addRow(QLabel(etiqueta), QLabel(str(valor)))
        boton_cerrar = QDialogButtonBox(QDialogButtonBox.Ok)
        boton_cerrar.accepted.connect(self.accept)
        layout.addWidget(boton_cerrar)

# --- Diálogo para Agregar/Editar Estudiante ---
class DialogoEstudiante(QDialog):
    """Diálogo para crear o editar la información de un estudiante."""
    datos_estudiante_listos = Signal(dict)
    def __init__(self, parent=None, datos_estudiante=None):
        super().__init__(parent)
        self.es_modo_edicion = datos_estudiante is not None
        titulo = "Editar Estudiante Becado" if self.es_modo_edicion else "Agregar Estudiante Becado"
        self.setWindowTitle(titulo)
        self.diseno_formulario = QFormLayout()
        self.cedula_input = QLineEdit()
        self.tipo_cedula_combo = QComboBox()
        self.tipo_cedula_combo.addItems(['V', 'E', 'P'])
        self.nombres_input = QLineEdit()
        self.apellidos_input = QLineEdit()
        self.carrera_combo = QComboBox()
        self.carrera_combo.addItems(CARRERAS)
        self.semestre_combo = QComboBox()
        self.semestre_combo.addItems(SEMESTRES.keys())
        self.etiqueta_estado = QLabel("")
        self.etiqueta_estado.setStyleSheet("color: green")
        self.diseno_formulario.addRow("T. Cédula:", self.tipo_cedula_combo)
        self.diseno_formulario.addRow("Cédula:", self.cedula_input)
        self.diseno_formulario.addRow("Nombres:", self.nombres_input)
        self.diseno_formulario.addRow("Apellidos:", self.apellidos_input)
        self.diseno_formulario.addRow("Carrera:", self.carrera_combo)
        self.diseno_formulario.addRow("Semestre:", self.semestre_combo)
        self.boton_guardar = QPushButton("Guardar")
        self.boton_cancelar = QPushButton("Cancelar")
        diseno_botones = QHBoxLayout()
        diseno_botones.addStretch(1)
        diseno_botones.addWidget(self.boton_guardar)
        diseno_botones.addWidget(self.boton_cancelar)
        diseno_botones.addStretch(1)
        self.boton_guardar.clicked.connect(self._accion_guardar)
        self.boton_cancelar.clicked.connect(self.reject)
        diseno_principal = QVBoxLayout(self)
        diseno_principal.addLayout(self.diseno_formulario)
        diseno_principal.addWidget(self.etiqueta_estado)
        diseno_principal.addLayout(diseno_botones)
        if self.es_modo_edicion: self.llenar_datos(datos_estudiante)

    def _accion_guardar(self):
        self.etiqueta_estado.clear()
        datos = self.obtener_datos()
        if datos:
            self.datos_estudiante_listos.emit(datos)

    def registrar_exito_y_limpiar(self, datos):
        """Muestra el mensaje de éxito y limpia el formulario."""
        self.etiqueta_estado.setText(f"¡Estudiante con CI {datos['tipo_cedula']}-{datos['cedula']} guardado!")
        self._limpiar_formulario()

    def _limpiar_formulario(self):
        self.cedula_input.clear()
        self.nombres_input.clear()
        self.apellidos_input.clear()
        self.tipo_cedula_combo.setCurrentIndex(0)
        self.carrera_combo.setCurrentIndex(0)
        self.semestre_combo.setCurrentIndex(0)
        self.tipo_cedula_combo.setFocus()

    def llenar_datos(self, datos):
        self.tipo_cedula_combo.setCurrentText(datos['tipo_cedula'])
        self.cedula_input.setText(str(datos['cedula']))
        self.nombres_input.setText(datos['nombres'])
        self.apellidos_input.setText(datos['apellidos'])
        self.carrera_combo.setCurrentText(datos['carrera'])
        self.semestre_combo.setCurrentText(next((k for k, v in SEMESTRES.items() if v == datos['semestre']), "CINU"))

    def obtener_datos(self):
        cedula_texto = self.cedula_input.text().strip()
        if not cedula_texto.isdigit() or not (6 <= len(cedula_texto) <= 9):
            mostrar_mensaje_advertencia("Dato Inválido", "La cédula debe contener solo números y tener entre 6 y 9 dígitos.")
            return None
        nombre = ' '.join(self.nombres_input.text().strip().split())
        apellido = ' '.join(self.apellidos_input.text().strip().split())
        regex_nombre_valido = re.compile(r"^[A-Za-zÀ-ÿ\s]+$")
        if not (3 <= len(nombre) <= 30 and regex_nombre_valido.match(nombre)):
            mostrar_mensaje_advertencia("Dato Inválido", "El nombre debe tener entre 3 y 30 caracteres, contener solo letras y espacios simples.")
            return None
        if not (3 <= len(apellido) <= 30 and regex_nombre_valido.match(apellido)):
            mostrar_mensaje_advertencia("Dato Inválido", "El apellido debe tener entre 3 y 30 caracteres, contener solo letras y espacios simples.")
            return None
        return {'tipo_cedula': self.tipo_cedula_combo.currentText(), 'cedula': int(cedula_texto),
                'nombres': nombre, 'apellidos': apellido, 'carrera': self.carrera_combo.currentText(),
                'semestre': SEMESTRES[self.semestre_combo.currentText()]}

# --- Ventana Principal ---
class AppGestorBecas(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestor de Estudiantes y Becas")
        self.setGeometry(100, 100, 1200, 700)
        
        if os.path.exists('icon.ico'):
            self.setWindowIcon(QIcon('icon.ico'))
            
        self.conexion_bd = sqlite3.connect(ARCHIVO_BD)
        self.conexion_bd.row_factory = sqlite3.Row
        self.todos_los_becados = []
        self.todos_los_inscritos = []
        self.encabezados_inscritos = []
        self._configurar_ui()
        self.cargar_estudiantes_becados()
        self.cargar_estudiantes_inscritos_desde_bd()

    def _configurar_ui(self):
        widget_principal = QWidget(self)
        self.setCentralWidget(widget_principal)
        diseno_principal = QHBoxLayout(widget_principal)
        grupo_inscritos = self.crear_grupo_tabla("Estudiantes Inscritos", "inscritos")
        self.tabla_inscritos, self.modelo_inscritos = self._crear_vista_tabla()
        self.tabla_inscritos.doubleClicked.connect(lambda index: self.ver_registro_doble_clic(index, 'inscritos'))
        grupo_inscritos.layout().addWidget(self.tabla_inscritos)
        grupo_becados = self.crear_grupo_tabla("Estudiantes Becados", "becados")
        self.tabla_becados, self.modelo_becados = self._crear_vista_tabla()
        self.tabla_becados.doubleClicked.connect(lambda index: self.ver_registro_doble_clic(index, 'becados'))
        grupo_becados.layout().addWidget(self.tabla_becados)
        diseno_principal.addWidget(grupo_inscritos, 1)
        diseno_principal.addWidget(grupo_becados, 1)

    def _crear_vista_tabla(self):
        tabla = QTableView()
        tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        modelo = QStandardItemModel()
        tabla.setModel(modelo)
        return tabla, modelo

    def crear_grupo_tabla(self, titulo, tipo_tabla):
        grupo = QGroupBox(titulo)
        layout = QVBoxLayout(grupo)
        
        controles_superiores = QHBoxLayout()
        
        boton_cargar = QPushButton("Cargar Registros")
        boton_cargar.clicked.connect(lambda: self.cargar_registros_a_tabla(tipo_tabla))
        controles_superiores.addWidget(boton_cargar)
        
        boton_limpiar = QPushButton("Limpiar Registros")
        boton_limpiar.clicked.connect(lambda: self.limpiar_registros_tabla(tipo_tabla))
        controles_superiores.addWidget(boton_limpiar)

        if tipo_tabla == "becados":
            boton_agregar = QPushButton("Agregar")
            boton_agregar.clicked.connect(self.agregar_estudiante_becado)
            controles_superiores.addWidget(boton_agregar)

            boton_editar = QPushButton("Editar")
            boton_editar.clicked.connect(self.editar_estudiante_becado)
            controles_superiores.addWidget(boton_editar)

            boton_eliminar = QPushButton("Eliminar")
            boton_eliminar.clicked.connect(self.eliminar_estudiante_becado)
            controles_superiores.addWidget(boton_eliminar)

            boton_exportar = QPushButton("Exportar")
            menu_exportar = QMenu(self)
            accion_excel = QAction("Exportar a Excel (.xlsx)", self)
            accion_excel.triggered.connect(lambda: self.exportar_datos('excel', tipo_tabla))
            menu_exportar.addAction(accion_excel)
            accion_csv = QAction("Exportar a CSV (.csv)", self)
            accion_csv.triggered.connect(lambda: self.exportar_datos('csv', tipo_tabla))
            menu_exportar.addAction(accion_csv)
            if PDF_DISPONIBLE:
                accion_pdf = QAction("Exportar a PDF (.pdf)", self)
                accion_pdf.triggered.connect(lambda: self.exportar_datos('pdf', tipo_tabla))
                menu_exportar.addAction(accion_pdf)
            boton_exportar.setMenu(menu_exportar)
            controles_superiores.addWidget(boton_exportar)

        layout.addLayout(controles_superiores)
        
        filtros_layout = QHBoxLayout()
        setattr(self, f"filtro_busqueda_{tipo_tabla}", QLineEdit())
        setattr(self, f"filtro_carrera_{tipo_tabla}", QComboBox())
        setattr(self, f"filtro_semestre_{tipo_tabla}", QComboBox())
        setattr(self, f"filtro_tipocedula_{tipo_tabla}", QComboBox())

        filtro_busqueda = getattr(self, f"filtro_busqueda_{tipo_tabla}")
        filtro_carrera = getattr(self, f"filtro_carrera_{tipo_tabla}")
        filtro_semestre = getattr(self, f"filtro_semestre_{tipo_tabla}")
        filtro_tipocedula = getattr(self, f"filtro_tipocedula_{tipo_tabla}")

        filtro_busqueda.setPlaceholderText("Buscar...")
        filtro_carrera.addItems(["Todas las Carreras"] + CARRERAS)
        filtro_semestre.addItems(["Todos los Semestres"] + list(SEMESTRES.keys()))
        filtro_tipocedula.addItems(["Todos los Tipos"] + ['V', 'E', 'P'])
        
        filtros_layout.addWidget(filtro_busqueda)
        filtros_layout.addWidget(filtro_carrera)
        filtros_layout.addWidget(filtro_semestre)
        filtros_layout.addWidget(filtro_tipocedula)

        filtro_busqueda.textChanged.connect(lambda: self._aplicar_filtros(tipo_tabla))
        filtro_carrera.currentTextChanged.connect(lambda: self._aplicar_filtros(tipo_tabla))
        filtro_semestre.currentTextChanged.connect(lambda: self._aplicar_filtros(tipo_tabla))
        filtro_tipocedula.currentTextChanged.connect(lambda: self._aplicar_filtros(tipo_tabla))
        layout.addLayout(filtros_layout)
        return grupo

    def _aplicar_filtros(self, tipo_tabla):
        filtro_carrera = getattr(self, f"filtro_carrera_{tipo_tabla}").currentText()
        filtro_semestre = getattr(self, f"filtro_semestre_{tipo_tabla}").currentText()
        filtro_tipocedula = getattr(self, f"filtro_tipocedula_{tipo_tabla}").currentText()
        texto_busqueda = normalizar_texto(getattr(self, f"filtro_busqueda_{tipo_tabla}").text())

        if tipo_tabla == 'becados':
            resultados = self.todos_los_becados
            if filtro_carrera != "Todas las Carreras":
                resultados = [r for r in resultados if r['carrera'] == filtro_carrera]
            if filtro_semestre != "Todos los Semestres":
                semestre_num = SEMESTRES.get(filtro_semestre)
                resultados = [r for r in resultados if r['semestre'] == semestre_num]
            if filtro_tipocedula != "Todos los Tipos":
                resultados = [r for r in resultados if r['tipo_cedula'] == filtro_tipocedula]
            if texto_busqueda:
                resultados = [r for r in resultados if texto_busqueda in str(r['cedula']) or
                              texto_busqueda in normalizar_texto(r['nombres']) or
                              texto_busqueda in normalizar_texto(r['apellidos'])]
            self.poblar_tabla_becados(resultados)
        
        elif tipo_tabla == 'inscritos':
            col_carrera = self.encabezados_inscritos.index("Carrera") if "Carrera" in self.encabezados_inscritos else -1
            col_semestre = self.encabezados_inscritos.index("Semestre") if "Semestre" in self.encabezados_inscritos else -1
            col_tipocedula = self.encabezados_inscritos.index("T. Cédula") if "T. Cédula" in self.encabezados_inscritos else -1

            for row in range(self.modelo_inscritos.rowCount()):
                mostrar_fila = True
                
                if filtro_carrera != "Todas las Carreras" and col_carrera != -1:
                    if self.modelo_inscritos.item(row, col_carrera).text() != filtro_carrera:
                        mostrar_fila = False
                
                if mostrar_fila and filtro_semestre != "Todos los Semestres" and col_semestre != -1:
                    if self.modelo_inscritos.item(row, col_semestre).text() != filtro_semestre:
                        mostrar_fila = False

                if mostrar_fila and filtro_tipocedula != "Todos los Tipos" and col_tipocedula != -1:
                    if self.modelo_inscritos.item(row, col_tipocedula).text() != filtro_tipocedula:
                        mostrar_fila = False
                
                if mostrar_fila and texto_busqueda:
                    fila_texto = "".join([self.modelo_inscritos.item(row, col).text() for col in range(self.modelo_inscritos.columnCount())])
                    if texto_busqueda not in normalizar_texto(fila_texto):
                        mostrar_fila = False
                
                self.tabla_inscritos.setRowHidden(row, not mostrar_fila)

    def poblar_tabla_becados(self, datos):
        self.modelo_becados.clear()
        self.modelo_becados.setHorizontalHeaderLabels(ENCABEZADOS_VISUALIZACION)
        if not datos:
            self.tabla_becados.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            return
        self.tabla_becados.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for datos_fila in datos:
            elementos_fila = []
            for col_index, h in enumerate(ENCABEZADOS_VISUALIZACION):
                valor = datos_fila.get({"T. Cédula": "tipo_cedula", "Cédula": "cedula", "Nombres": "nombres", "Apellidos": "apellidos", "Carrera": "carrera", "Semestre": "semestre"}[h], '')
                item_texto = next((k for k, v in SEMESTRES.items() if v == valor), "") if h == 'Semestre' else str(valor)
                elemento = QStandardItem(item_texto)
                if h == "T. Cédula": elemento.setData(datos_fila.get('id'), Qt.UserRole)
                if col_index in [0, 5]: elemento.setTextAlignment(Qt.AlignCenter)
                elementos_fila.append(elemento)
            self.modelo_becados.appendRow(elementos_fila)
        for i in range(len(ENCABEZADOS_VISUALIZACION)): self.tabla_becados.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch if i in [2,3,4] else QHeaderView.ResizeToContents)

    def _validar_dataframe_importado(self, df, is_csv=False):
        header_row_index, start_col_index = -1, -1
        for i, row in df.iterrows():
            if ENCABEZADOS_REQUERIDOS.issubset(set(row.astype(str).values)):
                header_row_index = i
                for j, col_name in enumerate(row.astype(str)):
                    if col_name in ENCABEZADOS_REQUERIDOS:
                        start_col_index = j; break
                break
        if header_row_index == -1:
            msg = ("No se encontraron los encabezados correctos en el archivo CSV.\n\n"
                   "Asegúrese de que su archivo use como separador ',' o ';' y contenga las siguientes columnas:\n\n"
                   if is_csv else "No se encontraron los encabezados correctos en el archivo.\n\n"
                   "Asegúrese de que la primera hoja contenga las siguientes columnas:\n\n")
            mostrar_mensaje_advertencia("Error de Formato", msg + f"{', '.join(ENCABEZADOS_VISUALIZACION)}")
            return None
        new_header = df.iloc[header_row_index, start_col_index:]
        df_limpio = df.iloc[header_row_index + 1:, start_col_index:].copy()
        df_limpio.columns = new_header
        df_limpio.dropna(axis=1, how='all', inplace=True); df_limpio.dropna(how='all', inplace=True)
        df_limpio = df_limpio.reset_index(drop=True)
        if df_limpio.empty:
            mostrar_mensaje_advertencia("Sin Datos", "No se encontraron registros de estudiantes debajo de los encabezados.")
            return None
        for i, fila in df_limpio.iterrows():
            try:
                if str(fila.get("T. Cédula", '')).strip().upper() not in ['V', 'E', 'P']: raise ValueError("T. Cédula debe ser 'V', 'E', o 'P'.")
                if not str(fila.get("Cédula", '')).strip().isdigit() or not (6 <= len(str(fila.get("Cédula", '')).strip()) <= 9): raise ValueError("La cédula debe contener solo números y tener entre 6 y 9 dígitos.")
                for campo in ["Nombres", "Apellidos"]:
                    valor = ' '.join(str(fila.get(campo, '')).strip().split())
                    if not (3 <= len(valor) <= 30 and re.match(r"^[A-Za-zÀ-ÿ\s]+$", valor)): raise ValueError(f"El campo '{campo}' no es válido.")
                if str(fila.get("Carrera", '')).strip() not in CARRERAS: raise ValueError("La carrera no es válida.")
                if str(fila.get("Semestre", '')).strip().upper() not in SEMESTRES: raise ValueError("El semestre no es válido.")
            except (ValueError, TypeError) as e:
                mostrar_mensaje_advertencia("Datos Inválidos", f"Error en la fila {i+1} del archivo: {e}")
                return None
        
        cedulas = df_limpio['Cédula']
        duplicados = cedulas[cedulas.duplicated(keep=False)]
        
        if not duplicados.empty:
            primer_duplicado = duplicados.iloc[0]
            indices_duplicados = duplicados[duplicados == primer_duplicado].index
            filas_reales = [i + header_row_index + 2 for i in indices_duplicados]
            filas_str = ', '.join(map(str, filas_reales))
            
            mostrar_mensaje_advertencia(
                "Cédulas Duplicadas",
                f"El archivo contiene cédulas duplicadas. La cédula '{primer_duplicado}' se encontró en las filas: {filas_str}.\n\n"
                "Por favor, corrige el archivo e inténtalo de nuevo."
            )
            return None
            
        return df_limpio

    def cargar_registros_a_tabla(self, tipo_tabla):
        cursor = self.conexion_bd.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {tipo_tabla}")
        if cursor.fetchone()[0] > 0:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Question); msg_box.setWindowTitle("Confirmar Sobrescritura")
            msg_box.setText(f"Ya existen registros en la tabla de '{tipo_tabla}'. Si cargas un nuevo archivo, los datos actuales se borrarán de forma permanente.\n\n¿Deseas continuar?")
            boton_si = msg_box.addButton("Sí", QMessageBox.YesRole); msg_box.addButton("No", QMessageBox.NoRole)
            msg_box.exec()
            if msg_box.clickedButton() != boton_si: return

        ruta_archivo, _ = QFileDialog.getOpenFileName(self, "Cargar Registros", "", "Archivos Soportados (*.xlsx *.xls *.csv)")
        if not ruta_archivo: return
        
        try:
            is_csv = ruta_archivo.endswith('.csv')
            if is_csv:
                try:
                    with open(ruta_archivo, 'r', encoding='utf-8') as f: first_line = f.readline()
                    sep = ';' if first_line.count(';') > first_line.count(',') else ','
                    df = pd.read_csv(ruta_archivo, header=None, dtype=str, sep=sep, encoding='utf-8')
                except (UnicodeDecodeError, KeyError):
                    with open(ruta_archivo, 'r', encoding='latin-1') as f: first_line = f.readline()
                    sep = ';' if first_line.count(';') > first_line.count(',') else ','
                    df = pd.read_csv(ruta_archivo, header=None, dtype=str, sep=sep, encoding='latin-1')
            else:
                df = pd.read_excel(ruta_archivo, sheet_name=0, header=None, dtype=str)
            
            df_validado = self._validar_dataframe_importado(df, is_csv=is_csv)
            if df_validado is None:
                return

            if tipo_tabla == 'inscritos':
                self.encabezados_inscritos = df_validado.columns.tolist()
                filas_dict = df_validado.to_dict('records')
                self.todos_los_inscritos = filas_dict
                filas_json = [json.dumps(r) for r in filas_dict]
                cursor.execute("DELETE FROM inscritos"); cursor.execute("DELETE FROM inscritos_encabezados")
                cursor.execute("INSERT INTO inscritos_encabezados (id, encabezados) VALUES (1, ?)", (json.dumps(self.encabezados_inscritos),))
                cursor.executemany("INSERT INTO inscritos (datos_fila) VALUES (?)", [(fila,) for fila in filas_json])
                self.conexion_bd.commit()
                self.cargar_estudiantes_inscritos_desde_bd()
                mostrar_mensaje_info("Éxito", f"Archivo '{os.path.basename(ruta_archivo)}' cargado y validado.")
            
            elif tipo_tabla == 'becados':
                try:
                    cursor.execute("BEGIN TRANSACTION")
                    cursor.execute("DELETE FROM becados")
                    df_validado['semestre_num'] = df_validado['Semestre'].str.upper().map(SEMESTRES)
                    for _, row in df_validado.iterrows():
                        cursor.execute(
                            "INSERT INTO becados (tipo_cedula, cedula, nombres, apellidos, carrera, semestre) VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                row['T. Cédula'], int(row['Cédula']), row['Nombres'],
                                row['Apellidos'], row['Carrera'], int(row['semestre_num'])
                            )
                        )
                    self.conexion_bd.commit()
                    self.cargar_estudiantes_becados()
                    mostrar_mensaje_info("Éxito", f"Estudiantes becados actualizados desde el archivo '{os.path.basename(ruta_archivo)}'.")
                except sqlite3.Error as e:
                    self.conexion_bd.rollback()
                    mostrar_error_critico("Error al Cargar Becados", f"Ocurrió un error al guardar los datos. Es posible que una cédula del archivo ya exista en la base de datos. Cambios revertidos.\n\nError: {e}")
                    self.cargar_estudiantes_becados()

        except Exception as e:
            mostrar_error_critico("Error de Carga", f"No se pudo procesar el archivo: {e}")

    def cargar_estudiantes_inscritos_desde_bd(self):
        try:
            cursor = self.conexion_bd.cursor()
            cursor.execute("SELECT encabezados FROM inscritos_encabezados WHERE id = 1")
            res_encabezados = cursor.fetchone()
            self.modelo_inscritos.clear(); self.modelo_inscritos.setHorizontalHeaderLabels([])
            if res_encabezados:
                self.encabezados_inscritos = json.loads(res_encabezados['encabezados'])
                cursor.execute("SELECT datos_fila FROM inscritos")
                self.todos_los_inscritos = [json.loads(fila['datos_fila']) for fila in cursor.fetchall()]
                self.poblar_tabla_inscritos(self.encabezados_inscritos, self.todos_los_inscritos)
        except (sqlite3.Error, json.JSONDecodeError) as e:
            mostrar_error_critico("Error de Base de Datos", f"No se pudieron cargar los estudiantes inscritos: {e}")

    def poblar_tabla_inscritos(self, encabezados, filas):
        self.modelo_inscritos.clear()
        self.modelo_inscritos.setHorizontalHeaderLabels(encabezados)
        if not filas:
            self.tabla_inscritos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            return
        self.tabla_inscritos.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for fila_datos in filas:
            elementos = [QStandardItem(str(fila_datos.get(enc, ''))) for enc in encabezados]
            for i, enc in enumerate(encabezados):
                if enc in ["T. Cédula", "Semestre"]: elementos[i].setTextAlignment(Qt.AlignCenter)
            self.modelo_inscritos.appendRow(elementos)
        for i in range(len(encabezados)): self.tabla_inscritos.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch if encabezados[i] not in ["T. Cédula", "Semestre"] else QHeaderView.ResizeToContents)

    def limpiar_registros_tabla(self, tipo_tabla):
        titulo = f"¿Estás seguro de limpiar el registro de los estudiantes de la tabla '{tipo_tabla}'?"
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Question); msg_box.setWindowTitle("Confirmar Limpieza"); msg_box.setText(titulo)
        boton_si = msg_box.addButton("Sí", QMessageBox.YesRole); msg_box.addButton("No", QMessageBox.NoRole)
        msg_box.exec()
        if msg_box.clickedButton() == boton_si:
            try:
                cursor = self.conexion_bd.cursor()
                if tipo_tabla == 'inscritos':
                    cursor.execute("DELETE FROM inscritos"); cursor.execute("DELETE FROM inscritos_encabezados")
                    self.conexion_bd.commit()
                    self.cargar_estudiantes_inscritos_desde_bd()
                else: # becados
                    cursor.execute("DELETE FROM becados")
                    self.conexion_bd.commit()
                    self.cargar_estudiantes_becados()
                mostrar_mensaje_info("Éxito", f"Se han borrado los registros de estudiantes {tipo_tabla}.")
            except sqlite3.Error as e:
                mostrar_error_critico("Error de DB", f"No se pudieron borrar los registros: {e}")

    def cargar_estudiantes_becados(self):
        try:
            cursor = self.conexion_bd.cursor()
            cursor.execute("SELECT id, tipo_cedula, cedula, nombres, apellidos, carrera, semestre FROM becados ORDER BY id")
            self.todos_los_becados = [dict(fila) for fila in cursor.fetchall()]
            self.poblar_tabla_becados(self.todos_los_becados)
        except sqlite3.Error as e:
            mostrar_error_critico("Error de Base de Datos", f"No se pudieron cargar los datos: {e}")

    def agregar_estudiante_becado(self):
        dialogo = DialogoEstudiante(self)
        dialogo.datos_estudiante_listos.connect(
            lambda datos: self._manejar_datos_agregar_estudiante(dialogo, datos)
        )
        dialogo.exec()

    def _manejar_datos_agregar_estudiante(self, dialogo, datos):
        try:
            cursor = self.conexion_bd.cursor()
            cursor.execute("INSERT INTO becados (tipo_cedula, cedula, nombres, apellidos, carrera, semestre) VALUES (?, ?, ?, ?, ?, ?)",
                           (datos['tipo_cedula'], datos['cedula'], datos['nombres'], datos['apellidos'], datos['carrera'], datos['semestre']))
            self.conexion_bd.commit()
            self.cargar_estudiantes_becados()
            dialogo.registrar_exito_y_limpiar(datos)
        except sqlite3.IntegrityError:
            mostrar_mensaje_advertencia("Error", f"La cédula {datos['cedula']} ya está registrada.")
        except sqlite3.Error as e:
            mostrar_error_critico("Error de DB", f"No se pudo agregar el estudiante: {e}")
            
    def ver_registro_doble_clic(self, index, tipo_tabla):
        if tipo_tabla == 'becados':
            id_estudiante = self.modelo_becados.item(index.row(), 0).data(Qt.UserRole)
            if id_estudiante is None: return
            datos_estudiante_db = next((r for r in self.todos_los_becados if r['id'] == id_estudiante), None)
            if datos_estudiante_db:
                datos_para_dialogo = {'T. Cédula': datos_estudiante_db.get('tipo_cedula'), 'Cédula': datos_estudiante_db.get('cedula'),
                                      'Nombres': datos_estudiante_db.get('nombres'), 'Apellidos': datos_estudiante_db.get('apellidos'),
                                      'Carrera': datos_estudiante_db.get('carrera'), 
                                      'Semestre': next((k for k, v in SEMESTRES.items() if v == datos_estudiante_db.get('semestre')), "N/A")}
                DialogoVerEstudiante(self, datos_estudiante=datos_para_dialogo).exec()
        elif tipo_tabla == 'inscritos':
            datos_para_dialogo = {self.modelo_inscritos.headerData(col, Qt.Horizontal): self.modelo_inscritos.item(index.row(), col).text()
                                  for col in range(self.modelo_inscritos.columnCount())}
            DialogoVerEstudiante(self, datos_estudiante=datos_para_dialogo).exec()

    def editar_estudiante_becado(self):
        filas_seleccionadas = self.tabla_becados.selectionModel().selectedRows()
        if not filas_seleccionadas:
            mostrar_mensaje_advertencia("Atención", "Selecciona un estudiante para editar.")
            return
        id_estudiante = self.modelo_becados.item(filas_seleccionadas[0].row(), 0).data(Qt.UserRole)
        if id_estudiante is None: return
        try:
            cursor = self.conexion_bd.cursor()
            cursor.execute("SELECT * FROM becados WHERE id = ?", (id_estudiante,))
            datos_estudiante = dict(cursor.fetchone())
            dialogo = DialogoEstudiante(self, datos_estudiante=datos_estudiante)
            dialogo.datos_estudiante_listos.connect(
                lambda datos: self._manejar_datos_editar_estudiante(dialogo, id_estudiante, datos)
            )
            dialogo.exec()
        except sqlite3.Error as e:
            mostrar_error_critico("Error de DB", f"No se pudo cargar para editar: {e}")

    def _manejar_datos_editar_estudiante(self, dialogo, id_estudiante, datos):
        try:
            cursor = self.conexion_bd.cursor()
            cursor.execute("UPDATE becados SET tipo_cedula=?, cedula=?, nombres=?, apellidos=?, carrera=?, semestre=? WHERE id=?",
                           (datos['tipo_cedula'], datos['cedula'], datos['nombres'], datos['apellidos'], datos['carrera'], datos['semestre'], id_estudiante))
            self.conexion_bd.commit()
            self.cargar_estudiantes_becados()
            dialogo.accept()
            mostrar_mensaje_info("Éxito", "Estudiante actualizado.")
        except sqlite3.IntegrityError:
            mostrar_mensaje_advertencia("Error", f"La cédula {datos['cedula']} ya existe para otro estudiante.")
        except sqlite3.Error as e:
            mostrar_error_critico("Error de DB", f"No se pudo actualizar: {e}")

    def eliminar_estudiante_becado(self):
        filas_seleccionadas = self.tabla_becados.selectionModel().selectedRows()
        if not filas_seleccionadas:
            mostrar_mensaje_advertencia("Atención", "Selecciona un estudiante para eliminar.")
            return
        id_estudiante = self.modelo_becados.item(filas_seleccionadas[0].row(), 0).data(Qt.UserRole)
        nombre = self.modelo_becados.item(filas_seleccionadas[0].row(), 2).text()
        if id_estudiante is None: return
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Question); msg_box.setWindowTitle("Confirmar Eliminación")
        msg_box.setText(f"¿Seguro que quieres eliminar a {nombre}?")
        boton_si = msg_box.addButton("Sí", QMessageBox.YesRole); msg_box.addButton("No", QMessageBox.NoRole)
        msg_box.exec()
        if msg_box.clickedButton() == boton_si:
            try:
                cursor = self.conexion_bd.cursor()
                cursor.execute("DELETE FROM becados WHERE id = ?", (id_estudiante,))
                self.conexion_bd.commit()
                self.cargar_estudiantes_becados()
                mostrar_mensaje_info("Éxito", "Estudiante eliminado.")
            except sqlite3.Error as e:
                mostrar_error_critico("Error de DB", f"No se pudo eliminar: {e}")

    def obtener_datos_df(self, tipo_tabla):
        if tipo_tabla == 'becados':
            if not self.todos_los_becados: return pd.DataFrame()
            df = pd.DataFrame(self.todos_los_becados)
            df['Semestre'] = df['semestre'].map({v: k for k, v in SEMESTRES.items()})
            df.rename(columns={'tipo_cedula': 'T. Cédula', 'cedula': 'Cédula', 'nombres': 'Nombres', 'apellidos': 'Apellidos', 'carrera': 'Carrera'}, inplace=True)
            df['Cédula'] = pd.to_numeric(df['Cédula'], errors='coerce')
            df['Semestre'] = df['Semestre'].apply(lambda x: str(x) if pd.notna(x) else "")
            return df[['T. Cédula', 'Cédula', 'Nombres', 'Apellidos', 'Carrera', 'Semestre']]
        elif tipo_tabla == 'inscritos':
            if not self.todos_los_inscritos: return pd.DataFrame()
            df = pd.DataFrame(self.todos_los_inscritos)
            if "Semestre" in df.columns: df["Semestre"] = pd.to_numeric(df["Semestre"], errors='coerce').fillna(df["Semestre"])
            return df

    def exportar_datos(self, formato, tipo_tabla):
        modelo = self.modelo_becados if tipo_tabla == 'becados' else self.modelo_inscritos
        if modelo.rowCount() == 0:
            mostrar_mensaje_advertencia("Atención", f"No hay estudiantes {tipo_tabla} para exportar.")
            return
        df = self.obtener_datos_df(tipo_tabla)
        if df.empty:
            mostrar_mensaje_advertencia("Atención", "No hay datos para exportar.")
            return

        default_filename = f"reporte_{tipo_tabla}.{formato if formato != 'excel' else 'xlsx'}"
        file_filter = f"Archivos {formato.upper()} (*.{formato if formato != 'excel' else 'xlsx'})"
        if formato == 'excel': save_func = lambda path: df.to_excel(path, index=False)
        elif formato == 'csv': save_func = lambda path: df.to_csv(path, index=False, encoding='utf-8-sig')
        elif formato == 'pdf':
            def save_func(path):
                df_pdf = df.astype(str)
                doc = SimpleDocTemplate(path)
                story = [Paragraph(f"Reporte de Estudiantes {tipo_tabla.capitalize()}", getSampleStyleSheet()['h1']), Spacer(1, 0.2*inch)]
                table = Table([df_pdf.columns.tolist()] + df_pdf.values.tolist())
                table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.grey), ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
                                           ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                                           ('BOTTOMPADDING', (0,0), (-1,0), 12), ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                                           ('GRID', (0,0), (-1,-1), 1, colors.black)]))
                story.append(table)
                doc.build(story)
        ruta_guardado, _ = QFileDialog.getSaveFileName(self, f"Guardar Reporte {formato.upper()}", default_filename, file_filter)
        if not ruta_guardado: return
        try:
            save_func(ruta_guardado)
            mostrar_mensaje_info("Éxito", f"Reporte guardado en '{ruta_guardado}'.")
        except PermissionError:
            mostrar_error_critico(f"Error al Exportar {formato.upper()}", "No se pudo guardar el archivo. Asegúrate de que el archivo no esté abierto en otro programa (como Excel) y vuelve a intentarlo.")
        except Exception as e:
            mostrar_error_critico(f"Error al Exportar {formato.upper()}", f"No se pudo guardar el reporte: {e}")

    def closeEvent(self, evento):
        self.conexion_bd.close()
        evento.accept()

def mostrar_cuadro_mensaje(icono, titulo, texto):
    msg_box = QMessageBox()
    if os.path.exists('icon.ico'):
        msg_box.setWindowIcon(QIcon('icon.ico'))
    msg_box.setIcon(icono); msg_box.setText(texto); msg_box.setWindowTitle(titulo)
    msg_box.exec()

def mostrar_mensaje_info(titulo, texto): mostrar_cuadro_mensaje(QMessageBox.Information, titulo, texto)
def mostrar_mensaje_advertencia(titulo, texto): mostrar_cuadro_mensaje(QMessageBox.Warning, titulo, texto)
def mostrar_error_critico(titulo, texto): mostrar_cuadro_mensaje(QMessageBox.Critical, titulo, texto)

if __name__ == '__main__':
    if not PDF_DISPONIBLE:
        mostrar_mensaje_advertencia("Dependencia Faltante", "La librería 'reportlab' no está instalada.\nLa exportación a PDF no estará disponible.\n\nPara activarla, instala con: pip install reportlab")
    inicializar_bd()
    app = QApplication(sys.argv)
    ventana = AppGestorBecas()
    ventana.show()
    sys.exit(app.exec())
