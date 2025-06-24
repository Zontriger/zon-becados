import sys
import re
import sqlite3
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QGroupBox, QFileDialog, QMessageBox, QTableView, 
    QAbstractItemView, QHeaderView, QDialog, QLineEdit, QComboBox,
    QFormLayout, QDialogButtonBox, QLabel
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt, Signal

# --- Dependencia Adicional para PDF ---
try:
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# --- Constantes ---
CARRERAS = [
    "Ingeniería de Sistemas", "Ingeniería de Telecomunicaciones", 
    "Ingeniería Eléctrica", "Contaduría", "Administración de Desastres"
]
SEMESTRES = {
    "CINU": 0, "1": 1, "2": 2, "3": 3, "4": 4, 
    "5": 5, "6": 6, "7": 7, "8": 8
}
DB_FILE = 'estudiantes.db'
DISPLAY_HEADERS = ["Cédula", "T. Cédula", "Nombres", "Apellidos", "Carrera", "Semestre"]

# --- Lógica de la Base de Datos ---
def init_db():
    """Inicializa la base de datos y crea la tabla si no existe."""
    try:
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS becados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_cedula TEXT NOT NULL CHECK(tipo_cedula IN ('V', 'E', 'P')),
                cedula INTEGER UNIQUE NOT NULL,
                nombres TEXT NOT NULL,
                apellidos TEXT NOT NULL,
                carrera TEXT NOT NULL,
                semestre INTEGER NOT NULL CHECK(semestre BETWEEN 0 AND 8)
            )
        ''')
        con.commit()
        con.close()
    except sqlite3.Error as e:
        show_critical_error("Error de Base de Datos", f"No se pudo inicializar la base de datos: {e}")
        sys.exit(1)

# --- Diálogo para Añadir/Editar Estudiante ---
class StudentDialog(QDialog):
    """Diálogo para crear o editar la información de un estudiante."""
    # Señal que se emite cuando los datos están listos para ser guardados
    student_data_ready = Signal(dict)

    def __init__(self, parent=None, student_data=None):
        super().__init__(parent)
        self.is_edit_mode = student_data is not None
        title = "Editar Estudiante Becado" if self.is_edit_mode else "Añadir Estudiante Becado"
        self.setWindowTitle(title)

        self.form_layout = QFormLayout()
        
        # --- Widgets del formulario ---
        self.tipo_cedula_combo = QComboBox()
        self.tipo_cedula_combo.addItems(['V', 'E', 'P'])
        self.cedula_input = QLineEdit()
        self.nombres_input = QLineEdit()
        self.apellidos_input = QLineEdit()
        self.carrera_combo = QComboBox()
        self.carrera_combo.addItems(CARRERAS)
        self.semestre_combo = QComboBox()
        self.semestre_combo.addItems(SEMESTRES.keys())
        self.status_label = QLabel("") # Para mostrar mensajes de éxito
        self.status_label.setStyleSheet("color: green")

        self.form_layout.addRow("T. Cédula:", self.tipo_cedula_combo)
        self.form_layout.addRow("Cédula:", self.cedula_input)
        self.form_layout.addRow("Nombres:", self.nombres_input)
        self.form_layout.addRow("Apellidos:", self.apellidos_input)
        self.form_layout.addRow("Carrera:", self.carrera_combo)
        self.form_layout.addRow("Semestre:", self.semestre_combo)

        # --- Botones ---
        self.button_box = QDialogButtonBox()
        self.save_and_close_button = self.button_box.addButton("Guardar y Cerrar", QDialogButtonBox.AcceptRole)
        
        if not self.is_edit_mode:
            self.save_and_new_button = self.button_box.addButton("Guardar y Añadir Otro", QDialogButtonBox.ApplyRole)
            self.save_and_new_button.clicked.connect(self._save_and_new_slot)

        self.cancel_button = self.button_box.addButton(QDialogButtonBox.Cancel)

        self.button_box.accepted.connect(self._save_and_close_slot)
        self.button_box.rejected.connect(self.reject)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(self.form_layout)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.button_box)
        self.setLayout(main_layout)

        if self.is_edit_mode:
            self.fill_data(student_data)
    
    def _save_and_new_slot(self):
        """Valida, emite los datos y limpia el formulario para un nuevo ingreso."""
        self.status_label.clear()
        data = self.get_data()
        if data:
            self.student_data_ready.emit(data)
            self.status_label.setText(f"¡Estudiante con CI {data['cedula']} guardado!")
            self._clear_form()

    def _save_and_close_slot(self):
        """Valida, emite los datos y cierra el diálogo."""
        self.status_label.clear()
        data = self.get_data()
        if data:
            self.student_data_ready.emit(data)
            self.accept()
            
    def _clear_form(self):
        """Limpia los campos del formulario."""
        self.cedula_input.clear()
        self.nombres_input.clear()
        self.apellidos_input.clear()
        self.tipo_cedula_combo.setCurrentIndex(0)
        self.carrera_combo.setCurrentIndex(0)
        self.semestre_combo.setCurrentIndex(0)
        self.cedula_input.setFocus()

    def fill_data(self, data):
        """Llena el formulario para editar."""
        self.tipo_cedula_combo.setCurrentText(data['tipo_cedula'])
        self.cedula_input.setText(str(data['cedula']))
        self.nombres_input.setText(data['nombres'])
        self.apellidos_input.setText(data['apellidos'])
        self.carrera_combo.setCurrentText(data['carrera'])
        semestre_key = next((key for key, val in SEMESTRES.items() if val == data['semestre']), "CINU")
        self.semestre_combo.setCurrentText(semestre_key)

    def get_data(self):
        """Recupera y valida los datos del formulario."""
        cedula_str = self.cedula_input.text().strip()
        if not cedula_str.isdigit() or not (6 <= len(cedula_str) <= 9):
            show_warning_message("Dato Inválido", "La cédula debe contener solo números y tener entre 6 y 9 dígitos.")
            return None
        
        nombre = self.nombres_input.text().strip()
        apellido = self.apellidos_input.text().strip()
        name_regex = re.compile(r"^[A-Za-zÀ-ÿ\s]+$")
        if not (3 <= len(nombre) <= 30 and name_regex.match(nombre)):
            show_warning_message("Dato Inválido", "El nombre debe tener entre 3 y 30 caracteres y contener solo letras y espacios.")
            return None
        if not (3 <= len(apellido) <= 30 and name_regex.match(apellido)):
            show_warning_message("Dato Inválido", "El apellido debe tener entre 3 y 30 caracteres y contener solo letras y espacios.")
            return None
            
        return {
            'tipo_cedula': self.tipo_cedula_combo.currentText(),
            'cedula': int(cedula_str),
            'nombres': ' '.join(nombre.split()),
            'apellidos': ' '.join(apellido.split()),
            'carrera': self.carrera_combo.currentText(),
            'semestre': SEMESTRES[self.semestre_combo.currentText()]
        }

# --- Ventana Principal ---
class ScholarshipManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestor de Estudiantes y Becas")
        self.setGeometry(100, 100, 1200, 700)

        self.db_con = sqlite3.connect(DB_FILE)
        self.db_con.row_factory = sqlite3.Row
        
        self._setup_ui()
        self.load_scholarship_students()

    def _setup_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        enrolled_group = self.create_table_group("Estudiantes Inscritos (desde Excel)", "load_enrolled")
        self.enrolled_table, self.enrolled_model = self._create_table_view()
        enrolled_group.layout().addWidget(self.enrolled_table)
        
        scholarship_group = self.create_table_group("Estudiantes Becados (Base de Datos)", "scholarship")
        self.scholarship_table, self.scholarship_model = self._create_table_view()
        scholarship_group.layout().addWidget(self.scholarship_table)

        main_layout.addWidget(enrolled_group, 1)
        main_layout.addWidget(scholarship_group, 1)
        
    def _create_table_view(self):
        table = QTableView()
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        model = QStandardItemModel()
        table.setModel(model)
        return table, model

    def create_table_group(self, title, mode):
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        
        if mode == "load_enrolled":
            load_button = QPushButton("Cargar Archivo Excel")
            load_button.clicked.connect(self.load_enrolled_students)
            layout.addWidget(load_button)
        elif mode == "scholarship":
            buttons_layout = QHBoxLayout()
            add_button = QPushButton("Añadir")
            edit_button = QPushButton("Editar")
            delete_button = QPushButton("Eliminar")
            add_button.clicked.connect(self.add_scholarship_student)
            edit_button.clicked.connect(self.edit_scholarship_student)
            delete_button.clicked.connect(self.delete_scholarship_student)
            buttons_layout.addWidget(add_button)
            buttons_layout.addWidget(edit_button)
            buttons_layout.addWidget(delete_button)
            
            export_layout = QHBoxLayout()
            export_excel_button = QPushButton("Exportar a Excel")
            export_excel_button.clicked.connect(self.export_scholarship_excel)
            export_layout.addWidget(export_excel_button)

            if PDF_AVAILABLE:
                export_pdf_button = QPushButton("Exportar a PDF")
                export_pdf_button.clicked.connect(self.export_scholarship_pdf)
                export_layout.addWidget(export_pdf_button)
            
            layout.addLayout(buttons_layout)
            layout.addLayout(export_layout)
            
        return group

    def populate_scholarship_table(self, data):
        self.scholarship_model.clear()
        self.scholarship_model.setHorizontalHeaderLabels(DISPLAY_HEADERS)

        key_map = {
            "Cédula": "cedula", "T. Cédula": "tipo_cedula", "Nombres": "nombres", 
            "Apellidos": "apellidos", "Carrera": "carrera", "Semestre": "semestre"
        }

        for row_data in data:
            row_items = []
            for header in DISPLAY_HEADERS:
                key = key_map[header]
                val = row_data[key]
                
                if key == 'semestre':
                    semestre_key = next((k for k, v in SEMESTRES.items() if v == val), "")
                    item = QStandardItem(semestre_key)
                else:
                    item = QStandardItem(str(val))
                row_items.append(item)
            
            if row_items:
                row_items[0].setData(row_data['id'], Qt.UserRole)
            
            self.scholarship_model.appendRow(row_items)
        
        self.scholarship_table.setModel(self.scholarship_model)

    def load_enrolled_students(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo Excel", "", "Archivos de Excel (*.xlsx *.xls)")
        if not file_path: return
        try:
            df = pd.read_excel(file_path)
            self.enrolled_model.clear()
            self.enrolled_model.setHorizontalHeaderLabels(df.columns)
            for _, row in df.iterrows():
                items = [QStandardItem(str(field)) for field in row]
                self.enrolled_model.appendRow(items)
            show_info_message("Éxito", f"Archivo '{file_path.split('/')[-1]}' cargado.")
        except Exception as e:
            show_critical_error("Error de Carga", f"No se pudo cargar el archivo: {e}")

    def load_scholarship_students(self):
        try:
            cur = self.db_con.cursor()
            cur.execute("SELECT id, tipo_cedula, cedula, nombres, apellidos, carrera, semestre FROM becados ORDER BY id")
            students = cur.fetchall()
            self.populate_scholarship_table([dict(row) for row in students])
        except sqlite3.Error as e:
            show_critical_error("Error de Base de Datos", f"No se pudieron cargar los datos: {e}")

    def add_scholarship_student(self):
        dialog = StudentDialog(self)
        dialog.student_data_ready.connect(self._handle_add_student_data)
        dialog.exec()

    def _handle_add_student_data(self, data):
        try:
            cur = self.db_con.cursor()
            cur.execute(
                "INSERT INTO becados (tipo_cedula, cedula, nombres, apellidos, carrera, semestre) VALUES (?, ?, ?, ?, ?, ?)",
                (data['tipo_cedula'], data['cedula'], data['nombres'], data['apellidos'], data['carrera'], data['semestre'])
            )
            self.db_con.commit()
            self.load_scholarship_students()
        except sqlite3.IntegrityError:
            show_warning_message("Error", f"La cédula {data['cedula']} ya está registrada.")
        except sqlite3.Error as e:
            show_critical_error("Error de DB", f"No se pudo añadir el estudiante: {e}")

    def edit_scholarship_student(self):
        selected_rows = self.scholarship_table.selectionModel().selectedRows()
        if not selected_rows:
            show_warning_message("Atención", "Selecciona un estudiante para editar.")
            return

        row_index = selected_rows[0].row()
        student_id = self.scholarship_model.item(row_index, 0).data(Qt.UserRole)
        
        try:
            cur = self.db_con.cursor()
            cur.execute("SELECT * FROM becados WHERE id = ?", (student_id,))
            student_data = dict(cur.fetchone())

            dialog = StudentDialog(self, student_data=student_data)
            dialog.student_data_ready.connect(lambda data: self._handle_edit_student_data(student_id, data))
            dialog.exec()

        except sqlite3.Error as e:
            show_critical_error("Error de DB", f"No se pudo cargar para editar: {e}")
            
    def _handle_edit_student_data(self, student_id, data):
        try:
            cur = self.db_con.cursor()
            cur.execute(
                "UPDATE becados SET tipo_cedula=?, cedula=?, nombres=?, apellidos=?, carrera=?, semestre=? WHERE id=?",
                (data['tipo_cedula'], data['cedula'], data['nombres'], data['apellidos'], 
                 data['carrera'], data['semestre'], student_id)
            )
            self.db_con.commit()
            self.load_scholarship_students()
            show_info_message("Éxito", "Estudiante actualizado.")
        except sqlite3.IntegrityError:
            show_warning_message("Error", "La cédula ya existe para otro estudiante.")
        except sqlite3.Error as e:
            show_critical_error("Error de DB", f"No se pudo actualizar: {e}")

    def delete_scholarship_student(self):
        selected_rows = self.scholarship_table.selectionModel().selectedRows()
        if not selected_rows:
            show_warning_message("Atención", "Selecciona un estudiante para eliminar.")
            return
            
        row_index = selected_rows[0].row()
        student_id = self.scholarship_model.item(row_index, 0).data(Qt.UserRole)
        nombre = self.scholarship_model.item(row_index, 2).text()

        reply = QMessageBox.question(self, "Confirmar", f"¿Seguro que quieres eliminar a {nombre}?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                cur = self.db_con.cursor()
                cur.execute("DELETE FROM becados WHERE id = ?", (student_id,))
                self.db_con.commit()
                self.load_scholarship_students()
                show_info_message("Éxito", "Estudiante eliminado.")
            except sqlite3.Error as e:
                show_critical_error("Error de DB", f"No se pudo eliminar: {e}")

    def get_scholarship_data_as_df(self):
        """Obtiene los datos de los becados como un DataFrame de Pandas con cabeceras amigables."""
        cur = self.db_con.cursor()
        cur.execute("SELECT cedula, tipo_cedula, nombres, apellidos, carrera, semestre FROM becados")
        students = cur.fetchall()
        if not students:
            return pd.DataFrame(columns=DISPLAY_HEADERS)

        df = pd.DataFrame([dict(row) for row in students])
        
        inv_semestres = {v: k for k, v in SEMESTRES.items()}
        df['semestre'] = df['semestre'].map(inv_semestres)
        
        column_rename_map = {
            'cedula': 'Cédula', 'tipo_cedula': 'T. Cédula', 'nombres': 'Nombres',
            'apellidos': 'Apellidos', 'carrera': 'Carrera', 'semestre': 'Semestre'
        }
        df.rename(columns=column_rename_map, inplace=True)
        
        return df[DISPLAY_HEADERS]

    def export_scholarship_excel(self):
        if self.scholarship_model.rowCount() == 0:
            show_warning_message("Atención", "No hay estudiantes para exportar.")
            return
        
        df = self.get_scholarship_data_as_df()
        save_path, _ = QFileDialog.getSaveFileName(self, "Guardar Reporte Excel", "reporte_becados.xlsx", "Archivos Excel (*.xlsx)")
        if not save_path: return

        try:
            df.to_excel(save_path, index=False)
            show_info_message("Éxito", f"Reporte guardado en '{save_path}'.")
        except Exception as e:
            show_critical_error("Error al Exportar", f"No se pudo guardar el reporte: {e}")

    def export_scholarship_pdf(self):
        if self.scholarship_model.rowCount() == 0:
            show_warning_message("Atención", "No hay estudiantes para exportar.")
            return
            
        save_path, _ = QFileDialog.getSaveFileName(self, "Guardar Reporte PDF", "reporte_becados.pdf", "Archivos PDF (*.pdf)")
        if not save_path: return

        try:
            doc = SimpleDocTemplate(save_path)
            styles = getSampleStyleSheet()
            story = []

            story.append(Paragraph("Reporte de Estudiantes Becados", styles['h1']))
            story.append(Spacer(1, 0.2*inch))

            df = self.get_scholarship_data_as_df()
            if df.empty:
                show_warning_message("Atención", "No hay datos para generar el PDF.")
                return

            table_data = [df.columns.tolist()] + df.values.tolist()
            
            table = Table(table_data)
            style = TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                ('GRID', (0,0), (-1,-1), 1, colors.black)
            ])
            table.setStyle(style)
            
            story.append(table)
            doc.build(story)
            show_info_message("Éxito", f"Reporte PDF guardado en '{save_path}'.")
        except Exception as e:
            show_critical_error("Error al Exportar PDF", f"No se pudo generar el PDF: {e}")

    def closeEvent(self, event):
        self.db_con.close()
        event.accept()

# --- Funciones de Mensajes ---
def show_message_box(icon, title, text):
    msg_box = QMessageBox()
    msg_box.setIcon(icon)
    msg_box.setText(text)
    msg_box.setWindowTitle(title)
    msg_box.exec()

def show_info_message(title, text): show_message_box(QMessageBox.Information, title, text)
def show_warning_message(title, text): show_message_box(QMessageBox.Warning, title, text)
def show_critical_error(title, text): show_message_box(QMessageBox.Critical, title, text)

# --- Punto de Entrada ---
if __name__ == '__main__':
    # --- Requisitos de instalación ---
    # pip install PySide6 pandas openpyxl reportlab
    if not PDF_AVAILABLE:
        show_warning_message(
            "Dependencia Faltante",
            "La librería 'reportlab' no está instalada.\n"
            "La exportación a PDF no estará disponible.\n\n"
            "Para activarla, instala con: pip install reportlab"
        )

    init_db()
    app = QApplication(sys.argv)
    window = ScholarshipManagerApp()
    window.show()
    sys.exit(app.exec())
