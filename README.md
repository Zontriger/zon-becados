# Gestor de Estudiantes y Becas (Zon-Becados)

Este es un programa de escritorio diseñado para facilitar la gestión y auditoría de listas de estudiantes, comparando un registro general de "Estudiantes Inscritos" con una lista oficial de "Estudiantes Becados".

La aplicación permite identificar visualmente qué estudiantes están en ambas listas, cuáles solo en una, y si existen discrepancias en sus datos, optimizando el proceso de validación de becas.

---

### **Información del Creador**

* **Autor**: Ricardo Pacheco
* **Sección**: 05S-2614-D1
* **Carrera**: Ingeniería de Sistemas
* **Universidad**: Universidad Nacional Experimental Politécnica de la Fuerza Armada (UNEFA)
* **Asignatura**: Lenguaje de Programación II

---

## ✨ Características Principales

* **Gestión Dual de Listas:** Administra y visualiza dos tablas de estudiantes por separado.
* **Comparación Inteligente:** Con un solo clic, colorea los registros para identificar concordancias, diferencias y errores en los datos.
* **Filtros Avanzados:** Busca por cualquier dato (nombre, cédula, etc.) y filtra por carrera, semestre o tipo de cédula. Los filtros de color permiten aislar problemas específicos.
* **Títulos Dinámicos:** Los títulos de las tablas se actualizan en tiempo real para reflejar el filtro activo y el número de registros visibles.
* **Exportación de Reportes:** Genera archivos en formato **Excel, CSV y PDF**. Si hay un filtro activo, el reporte solo incluirá los datos visibles.
* **Interfaz Adaptable:** La ventana se ajusta automáticamente al tamaño de la pantalla para una mejor experiencia de usuario.
* **Validación de Datos:** Sistema robusto que valida los datos al momento de cargar archivos, evitando errores de formato.

---

## 🚀 Manual de Usuario

### Instalación y Ejecución

Tienes dos maneras de utilizar este programa.

**Opción 1: Uso del Ejecutable (Recomendado)**

Esta es la forma más fácil y directa de usar la aplicación.

1.  Ve a la sección de **"Releases"** en el repositorio de GitHub del proyecto.
2.  Encontrarás dos archivos ZIP:
    * `ZonBecados_x64.zip`: Para sistemas operativos Windows de **64 bits** (la mayoría de las computadoras modernas).
    * `ZonBecados_x32.zip`: Para sistemas operativos Windows de **32 bits** (computadoras más antiguas).
3.  Descarga la versión que corresponda a tu computadora.
4.  Guarda el archivo en una carpeta de tu elección.
5.  **¡Listo!** Descomprime el ZIP, haz doble clic en el archivo `.exe` para iniciar el programa. La base de datos (`estudiantes.db`) se creará automáticamente en la misma carpeta.

**Opción 2: Ejecución desde el Código Fuente (Para Desarrolladores)**

Si deseas modificar el código o ejecutarlo en un entorno de desarrollo:

1.  Asegúrate de tener **Python** instalado.
2.  Clona o descarga este repositorio.
3.  Abre una terminal en la carpeta del proyecto e instala las dependencias usando el archivo `requirements` correspondiente a tu sistema.
4.  Una vez instaladas, ejecuta el programa con:
    ```bash
    python main.py
    ```

---

### Guía de Uso de la Interfaz

La ventana principal se divide en **Estudiantes Inscritos** (izquierda) y **Estudiantes Becados** (derecha).

#### **Carga de Archivos: Formato Requerido**

Para evitar errores, tus archivos de Excel (`.xlsx`) o CSV (`.csv`) **deben contener obligatoriamente** las siguientes columnas con estos nombres exactos:

| Columna            | Descripción y Reglas de Validación                                      | Ejemplo      |
| ------------------ | ------------------------------------------------------------------------- | ------------ |
| **T. Cédula** | Tipo de cédula. Solo acepta `V`, `E` o `P`.                             | `V`          |
| **Cédula** | Número de cédula. Debe ser un **número** de 6 a 9 dígitos.                | `29850926`   |
| **Nombres** | Nombres del estudiante. Texto de 3 a 30 caracteres, solo letras y espacios. | `Ana Barbara`|
| **Apellidos** | Apellidos del estudiante. Texto de 3 a 30 caracteres, solo letras y espacios. | `Borges Verenzuela`  |
| **Carrera** | Debe coincidir **exactamente** con una de las opciones del programa.      | `Contaduría` |
| **Semestre** | Acepta el número (`0` a `9`) o el nombre (`CINU`, `1`, `2`, etc.).           | `7`          |

> **Importante:**
> * Para archivos Excel, los datos **deben estar en la primera hoja** del libro.
> * El programa buscará esta cabecera en el archivo. Los datos de los estudiantes deben comenzar en la fila inmediatamente inferior. Cualquier fila o columna vacía antes de los datos puede causar problemas.

#### **Funcionalidades Principales**

1.  **Cargar y Limpiar Registros**: Usa los botones correspondientes en cada tabla para poblar o vaciar los datos desde tus archivos.

2.  **Filtros de Búsqueda**:
    * **Barra de búsqueda**: Escribe una o más palabras para buscar en todos los campos (ej: `ana contaduría`).
    * **Listas desplegables**: Selecciona una carrera, semestre o tipo de cédula para acotar los resultados.

3.  **Botón "Colorear Registros"**:
    * Activa el modo de comparación. Los colores tienen el siguiente significado:
        * **Verde**: El estudiante existe en **ambas** listas.
        * **Rojo**: El estudiante solo existe en **una** de las listas.
        * **Amarillo**: El estudiante está en ambas listas (verde), pero uno o más de sus datos (nombre, carrera, etc.) **no coinciden**. Las celdas específicas con la discrepancia se pintarán de amarillo.

4.  **Filtrar por Color**: Una vez coloreados los registros, usa los checkboxes "Verde", "Amarillo" o "Rojo" para aislar y analizar los casos que te interesen. Son excluyentes, solo puedes activar uno a la vez.

5.  **Títulos con Contadores**: El título de cada tabla siempre te mostrará cuántos registros son visibles en ese momento, actualizándose con cada filtro que apliques. `Ej: Estudiantes Becados (no inscritos) (4)`.

6.  **Exportar Reportes**: El botón "Exportar" en la tabla de becados te permite guardar los datos **actualmente visibles** en Excel, CSV o PDF. Si tienes un filtro de color activo, el título del reporte reflejará ese filtro.

7.  **Menú Superior**:
    * **Base de Datos**: Te permite guardar una copia de seguridad de tus datos, cargar una copia previa o limpiar toda la base de datos para empezar de cero.
    * **Ayuda**: Contiene este manual y un enlace al repositorio.

---

## 🛠️ Para Desarrolladores

### Librerías Utilizadas

* **PySide6 / PySide2**: Para la creación de la interfaz gráfica de usuario.
* **Pandas**: Para la manipulación, lectura y validación de datos.
* **openpyxl / xlrd**: Requeridos por Pandas para trabajar con archivos de Excel (`.xlsx` y `.xls`).
* **xlsxwriter**: Requerido por Pandas para escribir archivos Excel con formato.
* **ReportLab**: Para la generación de reportes en formato PDF.

### Compilación a `.exe`

Si has modificado el código y quieres generar un nuevo archivo ejecutable, asegúrate de tener `pyinstaller` instalado (`pip install pyinstaller`) y ejecuta el siguiente comando en la terminal desde la carpeta del proyecto:

```bash
pyinstaller --onefile --windowed --icon=icon.ico main.py
```

* `--onefile`: Empaqueta todo en un único archivo ejecutable.
* `--windowed`: Evita que se abra una consola de comandos al ejecutar la aplicación.
* `--icon=icon.ico`: Asigna el ícono de la aplicación.

El `.exe` final se encontrará en la carpeta `dist` que se creará automáticamente.

---

## 📄 Licencia y Contribuciones

Este proyecto es de código abierto. Siéntete libre de usarlo y modificarlo.

Si deseas contribuir, reportar un error o tienes alguna sugerencia, puedes hacerlo a través de la sección de **"Issues"** del repositorio en GitHub.