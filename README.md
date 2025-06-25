Gestor de Estudiantes y Becas (Zon-Becados)
===========================================

Este es un programa de escritorio desarrollado como parte de la asignatura Lenguaje de Programación II. Su principal objetivo es gestionar y comparar dos listas de estudiantes: una lista de "Estudiantes Inscritos" y una lista de "Estudiantes Becados".

La aplicación permite identificar visualmente qué estudiantes están en ambas listas, cuáles solo en una, y si existen discrepancias en sus datos, facilitando la auditoría y gestión de becas.

Información del Creador
-----------------------

* **Autor**: Ricardo Pacheco
* **Sección**: 05S-2614-D1
* **Carrera**: Ingeniería de Sistemas
* **Universidad**: Universidad Nacional Experimental Politécnica de la Fuerza Armada (UNEFA)
* **Asignatura**: Lenguaje de Programación II

Librerías Utilizadas
--------------------
* **PySide6**: Para la creación de la interfaz gráfica de usuario.
* **Pandas**: Para la manipulación y validación de datos.
* **openpyxl**: Requerido por Pandas para trabajar con archivos de Excel (.xlsx).
* **ReportLab**: Para la generación de reportes en formato PDF.

Manual de Usuario
=================

Instalación y Ejecución
-----------------------

Tienes dos maneras de utilizar este programa.

**Opción 1: Uso del Ejecutable (Recomendado para Usuarios)**

Esta es la forma más fácil y directa de usar la aplicación sin necesidad de instalar Python ni ninguna librería.

1.  Busca la sección de **"Releases"** en este repositorio de GitHub.
2.  Descarga el archivo `.exe` más reciente.
3.  Guarda el archivo en una carpeta de tu elección.
4.  ¡Listo! Haz doble clic en el archivo `.exe` para iniciar el programa. La base de datos (`estudiantes.db`) se creará automáticamente en la misma carpeta.

**Opción 2: Ejecución desde el Código Fuente (Para Desarrolladores)**

Si deseas modificar el código o ejecutarlo en un entorno de desarrollo, sigue estos pasos:

1.  Asegúrate de tener **Python** instalado en tu sistema.
2.  Clona o descarga este repositorio en tu computadora.
3.  Abre una terminal o línea de comandos en la carpeta del proyecto.
4.  Ejecuta el siguiente comando para instalar las librerías necesarias:
    `pip install -r requirements.txt`
5.  Una vez instaladas las dependencias, puedes ejecutar el programa con:
    `python main.py`

Interfaz y Funcionalidades
--------------------------

La ventana principal está dividida en dos secciones:

* **Estudiantes Inscritos (Izquierda)**: Carga y visualiza una lista general de estudiantes.
* **Estudiantes Becados (Derecha)**: Contiene la lista oficial de estudiantes con beca, la cual se puede gestionar manualmente.

**Funcionalidades Generales:**

* **Cargar Registros**: Permite seleccionar un archivo `.xlsx` o `.csv` para poblar cada tabla. Valida que los datos y columnas sean correctos.
    * **Límite de Becados**: No se pueden cargar más de 216 estudiantes en la tabla de becados.
* **Limpiar Registros**: Vacía la tabla correspondiente, previa confirmación.
* **Filtros**: Cada tabla tiene una barra de búsqueda y listas desplegables para filtrar por Carrera, Semestre y Tipo de Cédula.

**Funcionalidades (Solo para Estudiantes Becados):**

* **Agregar, Editar, Eliminar**: Permiten gestionar la lista de becados manualmente.
* **Exportar**: Guarda los datos de los becados en formato Excel, CSV o PDF.

**Funcionalidad Principal: Comparación**

* **Colorear Registros**: Este botón es el núcleo de la aplicación.
    * **Filas Verdes**: El estudiante existe en ambas listas.
    * **Filas Rojas**: El estudiante solo existe en una de las dos listas.
    * **Celdas Amarillas**: Si la fila es verde, resalta los campos específicos (nombre, carrera, etc.) que no coinciden entre las dos listas.
* **Filtrar por Color**: Una vez coloreado, puedes usar los checkboxes para mostrar solo las filas del color que te interese, facilitando la detección de inconsistencias.

**Recuentos y Estadísticas**

En la parte inferior se muestra un resumen en tiempo real de:
* Total de inscritos y becados.
* Becados no inscritos (se resalta en rojo si es mayor a cero).
* Estudiantes con datos incongruentes.
* Cupos para becas disponibles.

**Barra de Menú**

* **Base de Datos**: Opciones para Guardar una copia, Cargar una copia o Limpiar por completo la base de datos actual.
* **Ayuda**: Muestra una ventana con este manual y un enlace al repositorio en GitHub.

Contacto y Contribuciones
=========================

Este proyecto es de código abierto. Si deseas contribuir, reportar un error o tienes alguna sugerencia, puedes hacerlo a través de la sección de **"Issues"** del repositorio en GitHub.