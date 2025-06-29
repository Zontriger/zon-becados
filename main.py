import sys
import re
import sqlite3
import json
import os
import pandas as pd
import unicodedata
import shutil
import webbrowser
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QGroupBox, QFileDialog, QMessageBox, QTableView,
    QAbstractItemView, QHeaderView, QDialog, QLineEdit, QComboBox,
    QFormLayout, QDialogButtonBox, QLabel, QMenu, QCheckBox, QTextEdit,
    QButtonGroup
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction, QIcon, QColor, QBrush, QFont
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
    "Ingeniería de Sistemas", "Ingeniería de Telecomunicaciones", "Ingeniería Mecánica", 
    "Ingeniería Eléctrica", "Contaduría", "Administración de Desastres"
]
SEMESTRES = {
    "CINU": 0, "1": 1, "2": 2, "3": 3, "4": 4,
    "5": 5, "6": 6, "7": 7, "8": 8, "9": 9
}
ARCHIVO_BD = 'estudiantes.db'
ENCABEZADOS_VISUALIZACION = ["T. Cédula", "Cédula", "Nombres", "Apellidos", "Carrera", "Semestre"]
ENCABEZADOS_REQUERIDOS = set(ENCABEZADOS_VISUALIZACION)
LIMITE_BECADOS = 216

COLOR_VERDE_PASTEL = QColor(204, 255, 204)
COLOR_AMARILLO_PASTEL = QColor(255, 255, 204)
COLOR_ROJO_PASTEL = QColor(255, 204, 204)

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
                semestre INTEGER NOT NULL CHECK(semestre BETWEEN 0 AND 9)
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
    """Diálogo para mostrar la información completa de un estudiante y permitir acciones."""
    # Signals para comunicar acciones a la ventana principal
    agregar_a_becados = Signal()
    quitar_de_becados = Signal()
    editar_becado = Signal()

    def __init__(self, parent=None, datos_estudiante=None, tipo_tabla=None, ya_es_becado=False):
        super().__init__(parent)
        self.setWindowTitle("Información del Estudiante")
        self.setMinimumWidth(250)

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        mapa_etiquetas = {
            'T. Cédula': 'T. Cédula:', 'Cédula': 'Cédula:',
            'Nombres': 'Nombres:', 'Apellidos': 'Apellidos:',
            'Carrera': 'Carrera:', 'Semestre': 'Semestre:'
        }
        
        campos_conocidos = list(mapa_etiquetas.keys())
        campos_disponibles = list(datos_estudiante.keys())
        
        for campo in campos_conocidos:
            if campo in datos_estudiante:
                form_layout.addRow(QLabel(f"<b>{mapa_etiquetas[campo]}</b>"), QLabel(str(datos_estudiante[campo])))

        for campo in campos_disponibles:
            if campo not in campos_conocidos:
                form_layout.addRow(QLabel(f"<b>{campo}:</b>"), QLabel(str(datos_estudiante[campo])))

        main_layout.addLayout(form_layout)
        main_layout.addStretch(1)

        # Botón de acción superior (expandido)
        boton_accion_superior = None
        if tipo_tabla == 'inscritos':
            boton_accion_superior = QPushButton("Agregar a Becados")
            if ya_es_becado:
                boton_accion_superior.setText("Ya es Becado")
                boton_accion_superior.setEnabled(False)
                boton_accion_superior.setToolTip("Este estudiante ya se encuentra en la lista de becados.")
            else:
                boton_accion_superior.clicked.connect(self.agregar_a_becados.emit)
            
        elif tipo_tabla == 'becados':
            boton_accion_superior = QPushButton("Quitar de Becados")
            boton_accion_superior.clicked.connect(self.quitar_de_becados.emit)

        if boton_accion_superior:
            main_layout.addWidget(boton_accion_superior)
            
        # Layout para los botones inferiores (expandidos)
        layout_botones_inferior = QHBoxLayout()

        if tipo_tabla == 'becados':
            boton_editar = QPushButton("Editar")
            boton_editar.clicked.connect(self.editar_becado.emit)
            layout_botones_inferior.addWidget(boton_editar)

        boton_ok = QPushButton("OK")
        boton_ok.clicked.connect(self.accept)
        layout_botones_inferior.addWidget(boton_ok)
        
        main_layout.addLayout(layout_botones_inferior)


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
        nombre = ' '.join(self.nombres_input.text().strip().split()).title()
        apellido = ' '.join(self.apellidos_input.text().strip().split()).title()
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
        
        # --- Configuración dinámica del tamaño de la ventana ---
        screen = QApplication.primaryScreen()
        if screen:
            available_geometry = screen.availableGeometry()
            # Establecer un tamaño predeterminado del 85% del espacio disponible
            width = int(available_geometry.width() * 0.85)
            height = int(available_geometry.height() * 0.85)
            self.resize(width, height)
            
            # Centrar la ventana
            self.move(available_geometry.center() - self.rect().center())
        else:
            # Fallback a un tamaño fijo si no se puede obtener la pantalla
            self.resize(1200, 700)

        # Establecer un tamaño mínimo para la ventana
        self.setMinimumSize(1024, 600)

        if os.path.exists('icon.ico'):
            self.setWindowIcon(QIcon('icon.ico'))
        
        self.boton_agregar_becado = None
        self.modo_comparacion = False
        self.boton_comparar = None

        self.conexion_bd = sqlite3.connect(ARCHIVO_BD)
        self.conexion_bd.row_factory = sqlite3.Row
        self.todos_los_becados = []
        self.todos_los_inscritos = []
        self.encabezados_inscritos = []
        self._crear_barra_menu()
        self._configurar_ui()
        self.cargar_estudiantes_becados()
        self.cargar_estudiantes_inscritos_desde_bd()

    def _crear_barra_menu(self):
        menu_bar = self.menuBar()
        
        menu_db = menu_bar.addMenu("Base de Datos")
        accion_guardar = QAction("Guardar", self)
        accion_guardar.triggered.connect(self.guardar_bd)
        menu_db.addAction(accion_guardar)

        accion_cargar = QAction("Cargar", self)
        accion_cargar.triggered.connect(self.cargar_bd)
        menu_db.addAction(accion_cargar)
        
        menu_db.addSeparator()

        accion_limpiar = QAction("Limpiar", self)
        accion_limpiar.triggered.connect(self.limpiar_bd)
        menu_db.addAction(accion_limpiar)

        menu_ayuda = menu_bar.addMenu("Ayuda")
        accion_acerca_de = QAction("Acerca de", self)
        accion_acerca_de.triggered.connect(self.mostrar_acerca_de)
        menu_ayuda.addAction(accion_acerca_de)
        
        accion_github = QAction("GitHub", self)
        accion_github.triggered.connect(self.abrir_github)
        menu_ayuda.addAction(accion_github)

    def guardar_bd(self):
        if self.conexion_bd:
            self.conexion_bd.close()
            self.conexion_bd = None

        try:
            ruta_guardado, _ = QFileDialog.getSaveFileName(self, "Guardar Base de Datos", "copia_estudiantes.db", "Archivos de Base de Datos (*.db)")
            if ruta_guardado:
                shutil.copyfile(ARCHIVO_BD, ruta_guardado)
                mostrar_mensaje_info("Éxito", f"Base de datos guardada en:\n{ruta_guardado}")
        except Exception as e:
            mostrar_error_critico("Error al Guardar", f"No se pudo guardar la base de datos: {e}")
        finally:
            self.conexion_bd = sqlite3.connect(ARCHIVO_BD)
            self.conexion_bd.row_factory = sqlite3.Row

    def cargar_bd(self):
        ruta_archivo, _ = QFileDialog.getOpenFileName(self, "Cargar Base de Datos", "", "Archivos de Base de Datos (*.db)")
        if not ruta_archivo:
            return

        try:
            conn_test = sqlite3.connect(ruta_archivo)
            cursor_test = conn_test.cursor()
            cursor_test.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('becados', 'inscritos', 'inscritos_encabezados')")
            tables = cursor_test.fetchall()
            conn_test.close()
            if len(tables) < 3:
                raise sqlite3.DatabaseError("El archivo no contiene las tablas necesarias.")
        except Exception as e:
            mostrar_error_critico("Archivo Inválido", f"El archivo seleccionado no es una base de datos válida para esta aplicación.\n\nError: {e}")
            return

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("Confirmar Carga")
        msg_box.setText("Cargar una nueva base de datos reemplazará todos los datos actuales de forma permanente.\n\n¿Deseas continuar?")
        boton_si = msg_box.addButton("Sí, cargar", QMessageBox.YesRole)
        msg_box.addButton("No", QMessageBox.NoRole)
        msg_box.exec()

        if msg_box.clickedButton() == boton_si:
            if self.conexion_bd:
                self.conexion_bd.close()
            try:
                shutil.copyfile(ruta_archivo, ARCHIVO_BD)
                self.conexion_bd = sqlite3.connect(ARCHIVO_BD)
                self.conexion_bd.row_factory = sqlite3.Row
                self.cargar_estudiantes_becados()
                self.cargar_estudiantes_inscritos_desde_bd()
                mostrar_mensaje_info("Éxito", "Base de datos cargada correctamente.")
            except Exception as e:
                mostrar_error_critico("Error al Cargar", f"No se pudo cargar la base de datos: {e}")
                self.conexion_bd = sqlite3.connect(ARCHIVO_BD)
                self.conexion_bd.row_factory = sqlite3.Row

    def limpiar_bd(self):
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("Confirmar Limpieza Total")
        msg_box.setText("¿Estás seguro de que quieres borrar TODOS los registros (becados e inscritos) de la base de datos?\n\n¡Esta acción no se puede deshacer! Asegúrate de haber guardado una copia de seguridad si la necesitas.")
        boton_si = msg_box.addButton("Sí, borrar todo", QMessageBox.YesRole)
        msg_box.addButton("No", QMessageBox.NoRole)
        msg_box.exec()
        
        if msg_box.clickedButton() == boton_si:
            try:
                cursor = self.conexion_bd.cursor()
                cursor.execute("DELETE FROM becados")
                cursor.execute("DELETE FROM inscritos")
                cursor.execute("DELETE FROM inscritos_encabezados")
                self.conexion_bd.commit()
                
                self.cargar_estudiantes_becados()
                self.cargar_estudiantes_inscritos_desde_bd()
                
                mostrar_mensaje_info("Éxito", "Todos los registros han sido borrados de la base de datos.")
            except sqlite3.Error as e:
                mostrar_error_critico("Error de Base de Datos", f"No se pudieron borrar los registros: {e}")

    def mostrar_acerca_de(self):
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Acerca de Gestor de Becas")
        dialogo.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialogo)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        
        try:
            with open("README.md", "r", encoding="utf-8") as f:
                readme_content = f.read()
                text_edit.setMarkdown(readme_content)
        except FileNotFoundError:
            text_edit.setText("No se encontró el archivo README.md.")
        
        layout.addWidget(text_edit)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialogo.accept)
        layout.addWidget(button_box)
        
        dialogo.exec()

    def abrir_github(self):
        webbrowser.open("https://github.com/zontriger/zon-becados")

    def _configurar_ui(self):
        widget_principal = QWidget(self)
        self.setCentralWidget(widget_principal)
        diseno_principal = QVBoxLayout(widget_principal)

        layout_tablas = QHBoxLayout()
        grupo_inscritos = self.crear_grupo_tabla("Estudiantes Inscritos", "inscritos")
        self.tabla_inscritos, self.modelo_inscritos = self._crear_vista_tabla()
        self.tabla_inscritos.doubleClicked.connect(lambda index: self.ver_registro_doble_clic(index, 'inscritos'))
        grupo_inscritos.layout().addWidget(self.tabla_inscritos)
        
        grupo_becados = self.crear_grupo_tabla("Estudiantes Becados", "becados")
        self.tabla_becados, self.modelo_becados = self._crear_vista_tabla()
        self.tabla_becados.doubleClicked.connect(lambda index: self.ver_registro_doble_clic(index, 'becados'))
        grupo_becados.layout().addWidget(self.tabla_becados)

        layout_tablas.addWidget(grupo_inscritos, 1)
        layout_tablas.addWidget(grupo_becados, 1)
        diseno_principal.addLayout(layout_tablas)

        layout_controles_comp = QHBoxLayout()
        self.boton_comparar = QPushButton("Colorear Registros")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.boton_comparar.setFont(font)
        self.boton_comparar.setMinimumHeight(40)
        self.boton_comparar.clicked.connect(self.alternar_modo_comparacion)
        layout_controles_comp.addWidget(self.boton_comparar, 2)

        grupo_filtros_color = QGroupBox("Filtrar por Color")
        layout_filtros_color = QHBoxLayout()
        self.check_verde = QCheckBox("Verde")
        self.check_amarillo = QCheckBox("Amarillo")
        self.check_rojo = QCheckBox("Rojo")

        self.grupo_botones_color = QButtonGroup(self)
        self.grupo_botones_color.setExclusive(False)
        self.grupo_botones_color.addButton(self.check_verde)
        self.grupo_botones_color.addButton(self.check_amarillo)
        self.grupo_botones_color.addButton(self.check_rojo)
        self.grupo_botones_color.buttonClicked.connect(self._on_color_filter_clicked)

        layout_filtros_color.addStretch()
        layout_filtros_color.addWidget(self.check_verde)
        layout_filtros_color.addWidget(self.check_amarillo)
        layout_filtros_color.addWidget(self.check_rojo)
        layout_filtros_color.addStretch()
        grupo_filtros_color.setLayout(layout_filtros_color)
        layout_controles_comp.addWidget(grupo_filtros_color, 1)
        
        diseno_principal.addLayout(layout_controles_comp)

        layout_recuentos = QHBoxLayout()
        self.lbl_inscritos = QLabel("Estudiantes inscritos: --")
        self.lbl_becados = QLabel("Estudiantes becados: --")
        self.lbl_becados_no_inscritos = QLabel("Estudiantes becados no inscritos: --")
        self.lbl_incongruentes = QLabel("Estudiantes con datos incongruentes: --")
        self.lbl_cupos = QLabel("Cupos disponibles: --")
        
        for lbl in [self.lbl_inscritos, self.lbl_becados, self.lbl_becados_no_inscritos, self.lbl_incongruentes, self.lbl_cupos]:
            lbl.setAlignment(Qt.AlignCenter)
            layout_recuentos.addWidget(lbl)
        diseno_principal.addLayout(layout_recuentos)

    def _on_color_filter_clicked(self, clicked_button):
        """Maneja la selección exclusiva de los filtros de color."""
        if clicked_button.isChecked():
            for button in self.grupo_botones_color.buttons():
                if button is not clicked_button:
                    button.setChecked(False)
        self._aplicar_filtros()

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
            self.boton_agregar_becado = QPushButton("Agregar")
            self.boton_agregar_becado.clicked.connect(self.agregar_estudiante_becado)
            controles_superiores.addWidget(self.boton_agregar_becado)

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

        filtro_busqueda.textChanged.connect(self._aplicar_filtros)
        filtro_carrera.currentTextChanged.connect(self._aplicar_filtros)
        filtro_semestre.currentTextChanged.connect(self._aplicar_filtros)
        filtro_tipocedula.currentTextChanged.connect(self._aplicar_filtros)
        layout.addLayout(filtros_layout)
        return grupo
    
    def _actualizar_estado_botones(self):
        """Habilita o deshabilita botones según el estado de la aplicación."""
        count_becados = len(self.todos_los_becados)
        limite_alcanzado = count_becados >= LIMITE_BECADOS
        
        if self.boton_agregar_becado:
            self.boton_agregar_becado.setEnabled(not limite_alcanzado)
            if limite_alcanzado:
                self.boton_agregar_becado.setToolTip(f"Se ha alcanzado el límite de {LIMITE_BECADOS} estudiantes becados.")
            else:
                self.boton_agregar_becado.setToolTip("")

    def _aplicar_filtros(self):
        for tipo_tabla in ['becados', 'inscritos']:
            tabla = getattr(self, f"tabla_{tipo_tabla}")
            modelo = getattr(self, f"modelo_{tipo_tabla}")
            
            filtro_carrera = getattr(self, f"filtro_carrera_{tipo_tabla}").currentText()
            filtro_semestre = getattr(self, f"filtro_semestre_{tipo_tabla}").currentText()
            filtro_tipocedula = getattr(self, f"filtro_tipocedula_{tipo_tabla}").currentText()
            texto_busqueda_normalizado = normalizar_texto(getattr(self, f"filtro_busqueda_{tipo_tabla}").text())
            palabras_busqueda = texto_busqueda_normalizado.split()

            ver_verde = self.check_verde.isChecked()
            ver_amarillo = self.check_amarillo.isChecked()
            ver_rojo = self.check_rojo.isChecked()
            filtro_color_activo = self.modo_comparacion and (ver_verde or ver_amarillo or ver_rojo)

            for row in range(modelo.rowCount()):
                mostrar_por_texto = True
                fila_datos = {modelo.horizontalHeaderItem(col).text(): modelo.item(row, col).text() for col in range(modelo.columnCount())}
                
                if filtro_carrera != "Todas las Carreras" and fila_datos.get("Carrera") != filtro_carrera:
                    mostrar_por_texto = False
                if mostrar_por_texto and filtro_semestre != "Todos los Semestres" and fila_datos.get("Semestre") != filtro_semestre:
                    mostrar_por_texto = False
                if mostrar_por_texto and filtro_tipocedula != "Todos los Tipos" and fila_datos.get("T. Cédula") != filtro_tipocedula:
                    mostrar_por_texto = False
                
                if mostrar_por_texto and palabras_busqueda:
                    texto_completo_fila = normalizar_texto(" ".join(fila_datos.values()))
                    if not all(palabra in texto_completo_fila for palabra in palabras_busqueda):
                        mostrar_por_texto = False
                
                mostrar_final = mostrar_por_texto
                if mostrar_por_texto and filtro_color_activo:
                    mostrar_por_color = False
                    item_ejemplo = modelo.item(row, 0)
                    if item_ejemplo:
                        color_fila = item_ejemplo.background().color()
                        tiene_amarillo = any(modelo.item(row, col).background().color() == COLOR_AMARILLO_PASTEL for col in range(modelo.columnCount()))
                        
                        if ver_amarillo and tiene_amarillo:
                            mostrar_por_color = True
                        elif ver_verde and not tiene_amarillo and color_fila == COLOR_VERDE_PASTEL:
                            mostrar_por_color = True
                        elif ver_rojo and color_fila == COLOR_ROJO_PASTEL:
                            mostrar_por_color = True
                    
                    mostrar_final = mostrar_por_color

                tabla.setRowHidden(row, not mostrar_final)

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
                elemento.setData(datos_fila['cedula'], Qt.UserRole)
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
            fila_real = i + header_row_index + 2
            try:
                if str(fila.get("T. Cédula", '')).strip().upper() not in ['V', 'E', 'P']: raise ValueError("T. Cédula debe ser 'V', 'E', o 'P'.")
                if not str(fila.get("Cédula", '')).strip().isdigit() or not (6 <= len(str(fila.get("Cédula", '')).strip()) <= 9): raise ValueError("La cédula debe contener solo números y tener entre 6 y 9 dígitos.")
                for campo in ["Nombres", "Apellidos"]:
                    valor = ' '.join(str(fila.get(campo, '')).strip().split())
                    if not (3 <= len(valor) <= 30 and re.match(r"^[A-Za-zÀ-ÿ\s]+$", valor)): raise ValueError(f"El campo '{campo}' no es válido.")
                if str(fila.get("Carrera", '')).strip() not in CARRERAS: raise ValueError("La carrera no es válida.")
                if str(fila.get("Semestre", '')).strip().upper() not in SEMESTRES: raise ValueError("El semestre no es válido.")
            except (ValueError, TypeError) as e:
                mostrar_mensaje_advertencia("Datos Inválidos", f"Error en la fila {fila_real} del archivo: {e}")
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
        
        modelo_a_chequear = self.modelo_becados if tipo_tabla == 'becados' else self.modelo_inscritos
        if modelo_a_chequear.rowCount() > 0:
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
                if len(df_validado) > LIMITE_BECADOS:
                    mostrar_mensaje_advertencia("Límite Excedido", f"El archivo contiene {len(df_validado)} estudiantes, lo que supera el límite de {LIMITE_BECADOS} becados.")
                    return
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
        finally:
            self.actualizar_recuentos()
            if self.modo_comparacion:
                self.pintar_comparacion()
            self._aplicar_filtros()

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
        
        self.tabla_inscritos.resizeColumnsToContents()

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
            self._actualizar_estado_botones()
        except sqlite3.Error as e:
            mostrar_error_critico("Error de Base de Datos", f"No se pudieron cargar los datos: {e}")
        finally:
            self.actualizar_recuentos()
            if self.modo_comparacion:
                self.pintar_comparacion()
            self._aplicar_filtros()

    def agregar_estudiante_becado(self):
        if len(self.todos_los_becados) >= LIMITE_BECADOS:
            mostrar_mensaje_advertencia("Límite Alcanzado", f"No se pueden agregar más estudiantes becados. El límite es {LIMITE_BECADOS}.")
            return
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
            cedula = self.modelo_becados.item(index.row(), 1).text()
            datos_estudiante_db = next((r for r in self.todos_los_becados if str(r['cedula']) == cedula), None)
            if not datos_estudiante_db: return

            datos_para_dialogo = {
                'T. Cédula': datos_estudiante_db.get('tipo_cedula'),
                'Cédula': datos_estudiante_db.get('cedula'),
                'Nombres': datos_estudiante_db.get('nombres'),
                'Apellidos': datos_estudiante_db.get('apellidos'),
                'Carrera': datos_estudiante_db.get('carrera'),
                'Semestre': next((k for k, v in SEMESTRES.items() if v == datos_estudiante_db.get('semestre')), "N/A")
            }
            dialogo = DialogoVerEstudiante(self, datos_estudiante=datos_para_dialogo, tipo_tabla='becados')
            dialogo.quitar_de_becados.connect(lambda: self._accion_quitar_desde_dialogo(datos_estudiante_db, dialogo))
            dialogo.editar_becado.connect(lambda: self._accion_editar_desde_dialogo(datos_estudiante_db, dialogo))
            dialogo.exec()

        elif tipo_tabla == 'inscritos':
            datos_para_dialogo = {self.modelo_inscritos.horizontalHeaderItem(col).text(): self.modelo_inscritos.item(index.row(), col).text()
                                  for col in range(self.modelo_inscritos.columnCount())}

            cedula_inscrito = datos_para_dialogo.get('Cédula')
            cedulas_becados_set = {str(b['cedula']) for b in self.todos_los_becados}
            es_becado_actualmente = str(cedula_inscrito) in cedulas_becados_set if cedula_inscrito else False
            
            dialogo = DialogoVerEstudiante(self, datos_estudiante=datos_para_dialogo, tipo_tabla='inscritos', ya_es_becado=es_becado_actualmente)
            dialogo.agregar_a_becados.connect(lambda: self._accion_agregar_desde_dialogo(datos_para_dialogo, dialogo))
            dialogo.exec()

    def editar_estudiante_becado(self):
        filas_seleccionadas = self.tabla_becados.selectionModel().selectedRows()
        if not filas_seleccionadas:
            mostrar_mensaje_advertencia("Atención", "Selecciona un estudiante para editar.")
            return
        cedula_a_editar = self.modelo_becados.item(filas_seleccionadas[0].row(), 1).text()
        datos_estudiante = next((b for b in self.todos_los_becados if str(b['cedula']) == cedula_a_editar), None)
        self._editar_becado_con_datos(datos_estudiante)

    def _editar_becado_con_datos(self, datos_estudiante):
        if not datos_estudiante: return
        id_estudiante = datos_estudiante['id']
        dialogo = DialogoEstudiante(self, datos_estudiante=datos_estudiante)
        dialogo.datos_estudiante_listos.connect(
            lambda datos: self._manejar_datos_editar_estudiante(dialogo, id_estudiante, datos)
        )
        dialogo.exec()

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
        cedula_a_eliminar = self.modelo_becados.item(filas_seleccionadas[0].row(), 1).text()
        datos_estudiante = next((b for b in self.todos_los_becados if str(b['cedula']) == cedula_a_eliminar), None)
        if not datos_estudiante: return
        self._eliminar_becado_por_id(datos_estudiante['id'], datos_estudiante['nombres'])

    def _eliminar_becado_por_id(self, id_estudiante, nombre_estudiante):
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Question); msg_box.setWindowTitle("Confirmar Eliminación")
        msg_box.setText(f"¿Seguro que quieres eliminar a {nombre_estudiante} de la lista de becados?")
        boton_si = msg_box.addButton("Sí", QMessageBox.YesRole); msg_box.addButton("No", QMessageBox.NoRole)
        msg_box.exec()
        if msg_box.clickedButton() == boton_si:
            try:
                cursor = self.conexion_bd.cursor()
                cursor.execute("DELETE FROM becados WHERE id = ?", (id_estudiante,))
                self.conexion_bd.commit()
                self.cargar_estudiantes_becados()
                mostrar_mensaje_info("Éxito", "Estudiante eliminado.")
                return True
            except sqlite3.Error as e:
                mostrar_error_critico("Error de DB", f"No se pudo eliminar: {e}")
        return False

    def _accion_agregar_desde_dialogo(self, datos_inscrito, dialogo):
        dialogo.accept()
        if len(self.todos_los_becados) >= LIMITE_BECADOS:
            mostrar_mensaje_advertencia("Límite Alcanzado", f"No se pueden agregar más estudiantes becados. El límite es {LIMITE_BECADOS}.")
            return
        try:
            cedula_texto = datos_inscrito.get('Cédula', '').strip()
            if not cedula_texto.isdigit():
                mostrar_mensaje_advertencia("Dato Inválido", "La cédula del estudiante inscrito no es un número válido.")
                return
            cedula_int = int(cedula_texto)
            cursor = self.conexion_bd.cursor()
            cursor.execute("SELECT id FROM becados WHERE cedula = ?", (cedula_int,))
            if cursor.fetchone():
                mostrar_mensaje_advertencia("Duplicado", f"El estudiante con cédula {cedula_int} ya es un becado.")
                return

            datos_para_db = {
                'tipo_cedula': datos_inscrito.get('T. Cédula', 'V'), 'cedula': cedula_int,
                'nombres': ' '.join(datos_inscrito.get('Nombres', '').strip().split()).title(),
                'apellidos': ' '.join(datos_inscrito.get('Apellidos', '').strip().split()).title(),
                'carrera': datos_inscrito.get('Carrera', ''),
                'semestre': SEMESTRES.get(str(datos_inscrito.get('Semestre', '')).upper(), -1) # -1 para indicar error
            }

            errores = []
            if not datos_para_db['nombres']: errores.append("Nombres")
            if not datos_para_db['apellidos']: errores.append("Apellidos")
            if datos_para_db['carrera'] not in CARRERAS: errores.append("Carrera (no es válida)")
            
            if errores:
                mensaje_error = "No se puede agregar al estudiante. Faltan o son inválidos los siguientes datos:\n\n- " + "\n- ".join(errores)
                mostrar_mensaje_advertencia("Datos Faltantes o Inválidos", mensaje_error)
                return

        except (ValueError, KeyError) as e:
            mostrar_error_critico("Error de Datos", f"No se pudo procesar la información del estudiante inscrito: {e}")
            return
        try:
            cursor.execute("INSERT INTO becados (tipo_cedula, cedula, nombres, apellidos, carrera, semestre) VALUES (?, ?, ?, ?, ?, ?)",
                           (datos_para_db['tipo_cedula'], datos_para_db['cedula'], datos_para_db['nombres'], datos_para_db['apellidos'], datos_para_db['carrera'], datos_para_db['semestre']))
            self.conexion_bd.commit()
            self.cargar_estudiantes_becados()
            mostrar_mensaje_info("Éxito", f"Estudiante {datos_para_db['nombres']} {datos_para_db['apellidos']} ha sido agregado a los becados.")
        except sqlite3.Error as e:
            mostrar_error_critico("Error de DB", f"No se pudo agregar el estudiante: {e}")

    def _accion_quitar_desde_dialogo(self, datos_becado, dialogo):
        if self._eliminar_becado_por_id(datos_becado['id'], datos_becado['nombres']):
            dialogo.accept()

    def _accion_editar_desde_dialogo(self, datos_becado, dialogo):
        dialogo.accept()
        self._editar_becado_con_datos(datos_becado)

    def obtener_datos_df(self, tipo_tabla):
        if tipo_tabla == 'becados':
            if not self.todos_los_becados: return pd.DataFrame()
            df = pd.DataFrame(self.todos_los_becados)
            df.rename(columns={'tipo_cedula': 'T. Cédula', 'cedula': 'Cédula', 'nombres': 'Nombres', 'apellidos': 'Apellidos', 'carrera': 'Carrera', 'semestre':'Semestre'}, inplace=True)
            df['Cédula'] = pd.to_numeric(df['Cédula'], errors='coerce')
            df['Semestre'] = pd.to_numeric(df['Semestre'], errors='coerce')
            return df[['T. Cédula', 'Cédula', 'Nombres', 'Apellidos', 'Carrera', 'Semestre']]
        elif tipo_tabla == 'inscritos':
            if not self.todos_los_inscritos: return pd.DataFrame()
            df = pd.DataFrame(self.todos_los_inscritos)
            if 'Cédula' in df.columns:
                df['Cédula'] = pd.to_numeric(df['Cédula'], errors='coerce')
            if 'Semestre' in df.columns:
                df['Semestre'] = df['Semestre'].apply(lambda x: SEMESTRES.get(str(x).upper(), pd.NA))
                df['Semestre'] = pd.to_numeric(df['Semestre'], errors='coerce')
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
        if formato == 'excel': 
            def save_func(path):
                with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Reporte')
                    worksheet = writer.sheets['Reporte']
                    for i, col in enumerate(df.columns):
                        column_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
                        worksheet.set_column(i, i, column_len)
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

    def alternar_modo_comparacion(self):
        self.modo_comparacion = not self.modo_comparacion
        if self.modo_comparacion:
            self.pintar_comparacion()
            self.boton_comparar.setText("Quitar Coloreado")
        else:
            self.despintar_tablas()
            self.boton_comparar.setText("Colorear Registros")
        
        self.actualizar_recuentos()
        self._aplicar_filtros()

    def despintar_tablas(self):
        for row in range(self.modelo_becados.rowCount()):
            for col in range(self.modelo_becados.columnCount()):
                self.modelo_becados.item(row, col).setBackground(QBrush())
        
        for row in range(self.modelo_inscritos.rowCount()):
            for col in range(self.modelo_inscritos.columnCount()):
                self.modelo_inscritos.item(row, col).setBackground(QBrush())

    def pintar_comparacion(self):
        self.despintar_tablas()
        
        becados_map = {str(b['cedula']): b for b in self.todos_los_becados}
        inscritos_map = {str(i.get('Cédula')): i for i in self.todos_los_inscritos if 'Cédula' in i and i.get('Cédula')}
        
        cedulas_becados = set(becados_map.keys())
        cedulas_inscritos = set(inscritos_map.keys())
        cedulas_comunes = cedulas_becados.intersection(cedulas_inscritos)
        
        mismatched_fields = {}
        mapa_comparacion = {
            "T. Cédula": ('tipo_cedula', 'T. Cédula'),
            "Nombres": ('nombres', 'Nombres'),
            "Apellidos": ('apellidos', 'Apellidos'),
            "Carrera": ('carrera', 'Carrera'),
            "Semestre": ('semestre', 'Semestre')
        }
        
        for cedula in cedulas_comunes:
            becado_data = becados_map[cedula]
            inscrito_data = inscritos_map[cedula]
            mismatches = []
            
            for header, (key_becado, key_inscrito) in mapa_comparacion.items():
                val_becado = becado_data.get(key_becado)
                val_inscrito = inscrito_data.get(key_inscrito)
                
                if header == "Semestre":
                    val_inscrito = SEMESTRES.get(str(val_inscrito).upper(), -1)
                    
                if str(val_becado) != str(val_inscrito):
                    mismatches.append(header)
            
            if mismatches:
                mismatched_fields[cedula] = mismatches
                
        for row in range(self.modelo_becados.rowCount()):
            cedula = self.modelo_becados.item(row, 1).text()
            if cedula in cedulas_comunes:
                for col in range(self.modelo_becados.columnCount()):
                    self.modelo_becados.item(row, col).setBackground(QBrush(COLOR_VERDE_PASTEL))
                if cedula in mismatched_fields:
                    for col in range(self.modelo_becados.columnCount()):
                        header = self.modelo_becados.horizontalHeaderItem(col).text()
                        if header in mismatched_fields.get(cedula, []):
                            self.modelo_becados.item(row, col).setBackground(QBrush(COLOR_AMARILLO_PASTEL))
            else:
                for col in range(self.modelo_becados.columnCount()):
                    self.modelo_becados.item(row, col).setBackground(QBrush(COLOR_ROJO_PASTEL))

        if "Cédula" in self.encabezados_inscritos:
            cedula_col_idx = self.encabezados_inscritos.index('Cédula')
            for row in range(self.modelo_inscritos.rowCount()):
                cedula = self.modelo_inscritos.item(row, cedula_col_idx).text()
                if cedula in cedulas_comunes:
                    for col in range(self.modelo_inscritos.columnCount()):
                        self.modelo_inscritos.item(row, col).setBackground(QBrush(COLOR_VERDE_PASTEL))
                    if cedula in mismatched_fields:
                        for header_mismatch in mismatched_fields.get(cedula, []):
                            if header_mismatch in self.encabezados_inscritos:
                                col_mismatch = self.encabezados_inscritos.index(header_mismatch)
                                self.modelo_inscritos.item(row, col_mismatch).setBackground(QBrush(COLOR_AMARILLO_PASTEL))
                else:
                    for col in range(self.modelo_inscritos.columnCount()):
                        self.modelo_inscritos.item(row, col).setBackground(QBrush(COLOR_ROJO_PASTEL))
        
        self.actualizar_recuentos()

    def actualizar_recuentos(self):
        becados_map = {str(b['cedula']): b for b in self.todos_los_becados}
        inscritos_map = {str(i.get('Cédula')): i for i in self.todos_los_inscritos if 'Cédula' in i and i.get('Cédula')}
        
        cedulas_becados = set(becados_map.keys())
        cedulas_inscritos = set(inscritos_map.keys())

        num_inscritos = len(cedulas_inscritos)
        num_becados = len(cedulas_becados)

        self.lbl_inscritos.setText(f"Estudiantes inscritos: {num_inscritos if num_inscritos > 0 else '--'}")
        
        self.lbl_becados.setText(f"Estudiantes becados: {num_becados if num_becados > 0 else '--'}")
        self.lbl_becados.setStyleSheet("color: red;" if num_becados >= LIMITE_BECADOS else "")

        cupos_disponibles = LIMITE_BECADOS - num_becados
        if cupos_disponibles > 0:
            self.lbl_cupos.setText(f"Cupos disponibles: <b>{cupos_disponibles}</b>")
            self.lbl_cupos.setStyleSheet("color: green;")
        else:
            self.lbl_cupos.setText(f"Cupos disponibles: <b style='color: red;'>{cupos_disponibles}</b>")
            self.lbl_cupos.setStyleSheet("")

        if num_becados > 0 and num_inscritos > 0:
            cedulas_comunes = cedulas_becados.intersection(cedulas_inscritos)
            
            becados_no_inscritos_count = len(cedulas_becados - cedulas_inscritos)
            if becados_no_inscritos_count > 0:
                self.lbl_becados_no_inscritos.setText(f"Estudiantes becados no inscritos: <b>{becados_no_inscritos_count}</b>")
                self.lbl_becados_no_inscritos.setStyleSheet("color: red;")
            else:
                self.lbl_becados_no_inscritos.setText("Estudiantes becados no inscritos: 0")
                self.lbl_becados_no_inscritos.setStyleSheet("")
            
            incongruentes = 0
            if self.modo_comparacion:
                mapa_comparacion = {"T. Cédula": ('tipo_cedula', 'T. Cédula'), "Nombres": ('nombres', 'Nombres'), "Apellidos": ('apellidos', 'Apellidos'), "Carrera": ('carrera', 'Carrera'), "Semestre": ('semestre', 'Semestre')}
                for cedula in cedulas_comunes:
                    becado_data = becados_map[cedula]
                    inscrito_data = inscritos_map[cedula]
                    for header, (key_becado, key_inscrito) in mapa_comparacion.items():
                        val_becado = becado_data.get(key_becado)
                        val_inscrito = inscrito_data.get(key_inscrito)
                        if header == "Semestre":
                            val_inscrito = SEMESTRES.get(str(val_inscrito).upper(), -1)
                        if str(val_becado) != str(val_inscrito):
                            incongruentes += 1
                            break
            self.lbl_incongruentes.setText(f"Estudiantes con datos incongruentes: {incongruentes if self.modo_comparacion else '--'}")
        else:
            self.lbl_becados_no_inscritos.setText("Estudiantes becados no inscritos: --")
            self.lbl_becados_no_inscritos.setStyleSheet("")
            self.lbl_incongruentes.setText("Estudiantes con datos incongruentes: --")

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
    app = QApplication(sys.argv)
    
    if not PDF_DISPONIBLE:
        mostrar_mensaje_advertencia("Dependencia Faltante", "La librería 'reportlab' no está instalada.\nLa exportación a PDF no estará disponible.\n\nPara activarla, instala con: pip install reportlab")
    
    inicializar_bd()
    ventana = AppGestorBecas()
    ventana.show()
    sys.exit(app.exec())
