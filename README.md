# Gestor de Estudiantes y Becas (Zon-Becados)

Este es un programa de escritorio desarrollado como parte de la asignatura Lenguaje de Programación II. Su principal objetivo es gestionar y comparar dos listas de estudiantes: una lista de "Estudiantes Inscritos" (generalmente cargada desde un archivo) y una lista de "Estudiantes Becados" (gestionada manualmente o cargada desde un archivo dentro de la aplicación).

La aplicación permite identificar visualmente qué estudiantes están en ambas listas, cuáles solo en una, y si existen discrepancias en sus datos, facilitando la auditoría y gestión de becas.

### Información del Creador

* **Autor:** Ricardo Pacheco

* **Sección:** 05S-2614-D1

* **Carrera:** Ingeniería de Sistemas

* **Universidad:** Universidad Nacional Experimental Politécnica de la Fuerza Armada (UNEFA)

* **Asignatura:** Lenguaje de Programación II

### Librerías Utilizadas

Este proyecto utiliza las siguientes librerías de Python. Puedes instalarlas todas con el archivo `requirements.txt` proporcionado.

* **PySide6:** Para la creación de la interfaz gráfica de usuario.

* **Pandas:** Para la manipulación y validación de datos al cargar archivos de Excel/CSV.

* **openpyxl:** Requerido por Pandas para trabajar con archivos de Excel (`.xlsx`).

* **ReportLab:** Para la generación de reportes en formato PDF.

## Manual de Usuario

### Instalación

Para ejecutar este programa, primero debes instalar las dependencias necesarias.

1. Asegúrate de tener Python instalado en tu sistema.

2. Clona o descarga este repositorio en tu computadora.

3. Abre una terminal o línea de comandos en la carpeta del proyecto.

4. Ejecuta el siguiente comando para instalar las librerías:


pip install -r requirements.txt


### Ejecución

Una vez instaladas las dependencias, puedes ejecutar el programa con el siguiente comando en la terminal:


python main.py


### Interfaz Principal

La ventana principal está dividida en dos secciones principales, una al lado de la otra:

* **Estudiantes Inscritos (Izquierda):** Esta tabla se utiliza para cargar y visualizar una lista general de estudiantes, típicamente desde un archivo proporcionado por la institución.

* **Estudiantes Becados (Derecha):** Esta tabla contiene la lista oficial de los estudiantes que tienen una beca. Los datos aquí pueden ser agregados manualmente o cargados desde un archivo.

### Funcionalidades Generales

#### Cargar Registros

Ambas tablas tienen un botón **"Cargar Registros"**. Permite seleccionar un archivo `.xlsx` o `.csv`. El programa validará que el archivo contenga las columnas requeridas (`T. Cédula`, `Cédula`, `Nombres`, `Apellidos`, `Carrera`, `Semestre`) y que los datos en cada fila cumplan con los formatos correctos (ej: cédula numérica, semestre válido, etc.).

* **Límite de Becados:** No se pueden cargar más de 216 estudiantes en la tabla de becados. Si el archivo supera este límite, la carga será rechazada.

#### Limpiar Registros

El botón **"Limpiar Registros"** vacía todos los datos de la tabla correspondiente, tanto en la vista como en la base de datos. Se pedirá una confirmación antes de proceder.

#### Filtros

Cada tabla cuenta con filtros para refinar la búsqueda:

* **Barra de Búsqueda:** Busca coincidencias de texto en nombres, apellidos o cédula. La búsqueda es insensible a mayúsculas y acentos.

* **Listas Desplegables:** Permiten filtrar por Carrera, Semestre y Tipo de Cédula.

### Funcionalidades (Solo para Estudiantes Becados)

* **Agregar:** Abre una ventana para registrar un nuevo estudiante becado manualmente. Realiza validaciones para evitar datos incorrectos y cédulas duplicadas. Los nombres y apellidos se guardan automáticamente con la primera letra de cada palabra en mayúscula.

* **Editar:** Permite modificar los datos de un estudiante becado previamente seleccionado en la tabla.

* **Eliminar:** Borra el estudiante seleccionado de la base de datos, previa confirmación.

* **Exportar:** Permite guardar los datos de la tabla de becados en formato **Excel (`.xlsx`)**, **CSV (`.csv`)** o **PDF (`.pdf`)**.

### Funcionalidad Principal: Comparación

Debajo de las tablas se encuentran los controles para la comparación de datos.

#### Colorear Registros

Este es el botón central de la aplicación. Al presionarlo, las tablas se colorean de la siguiente manera:

* **Filas Verdes:** Indican que un estudiante existe en **ambas** tablas (Inscritos y Becados).

* **Filas Rojas:** Indican que un estudiante solo existe en **una** de las dos tablas.

* **Celdas Amarillas:** Si una fila es verde pero algún dato (nombre, apellido, carrera, etc.) no coincide exáctamente entre las dos listas, la celda específica con el dato diferente se pintará de amarillo en ambas tablas. La comparación es sensible a mayúsculas y acentos.

Presionar el botón de nuevo ("Quitar Coloreado") restaura los colores originales de las tablas.

#### Filtrar por Color

Una vez activado el modo de coloreado, puedes usar los checkboxes (Verde, Amarillo, Rojo) para filtrar las filas según su color. Esto permite aislar rápidamente los registros que te interesan, por ejemplo, mostrando solo los que tienen incongruencias (amarillo) o los que no están en ambas listas (rojo).

#### Recuentos y Estadísticas

En la parte inferior de la ventana, encontrarás un resumen en tiempo real con los datos más importantes:

* **Estudiantes inscritos:** Número total de estudiantes en la lista de la izquierda.

* **Estudiantes becados:** Número total de estudiantes en la lista de la derecha. El texto se pone en rojo si se alcanza el límite.

* **Estudiantes becados no inscritos:** Muestra cuántos estudiantes están en la lista de becados pero no en la de inscritos. Se pone en rojo si el valor es mayor a cero.

* **Estudiantes con datos incongruentes:** Muestra cuántos estudiantes que están en ambas listas tienen al menos un campo con información diferente.

* **Cupos disponibles:** Muestra cuántos cupos para becas quedan disponibles. El texto es verde si hay cupos y rojo si no los hay.

### Barra de Menú

#### Base de Datos

* **Guardar:** Permite guardar una copia de seguridad del archivo de base de datos (`estudiantes.db`) en la ubicación que elijas.
* **Cargar:** Permite reemplazar la base de datos actual con un archivo `.db` previamente guardado. El programa validará que sea un archivo compatible antes de realizar la carga.
* **Limpiar:** Borra **todos** los registros de ambas tablas de la base de datos. Se mostrará una advertencia clara antes de proceder, ya que esta acción no se puede deshacer.

#### Ayuda

* **Acerca de:** Muestra una ventana con el contenido de este manual de usuario.
* **GitHub:** Abre el repositorio del proyecto en tu navegador web para ver el código fuente.

---

### Contacto y Contribuciones

Este proyecto es de código abierto. Si deseas contribuir, reportar un error o tienes alguna sugerencia, puedes hacerlo a través de la sección de "Issues" del repositorio en [GitHub](https://github.com/zontriger/zon-becados).