# Face Lock — Bloqueo automático por reconocimiento facial

## Requisitos del sistema
- Windows 10 / 11
- Python 3.8 o superior
- Webcam

---

## Instalación de dependencias

### Opción A — Conda (más fácil en Windows)
```
conda install -c conda-forge dlib face_recognition opencv numpy
```

### Opción B — pip (requiere CMake + Visual C++ Build Tools)
1. Instala [CMake](https://cmake.org/download/) y [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)
2. Ejecuta:
```
pip install cmake dlib face_recognition opencv-python numpy
```

---

## Uso

### Paso 1: Registrar tu rostro (una sola vez)
```
python 1_registrar_rostro.py
```
Siéntate frente a la cámara con buena iluminación. El script capturará 30 muestras
y guardará tu perfil en `mi_rostro.pkl`.

### Paso 2: Activar la vigilancia
```
python 2_vigilancia.py
```

#### Opciones disponibles:
| Parámetro       | Descripción                                    | Default |
|-----------------|------------------------------------------------|---------|
| `--tolerancia`  | Umbral (menor = más estricto). Rango: 0.0–1.0 | `0.55`  |
| `--segundos`    | Tiempo sin reconocerte antes de bloquear       | `5`     |
| `--silencio`    | Ejecutar sin ventana (segundo plano)           | off     |

Ejemplo:
```
python 2_vigilancia.py --tolerancia 0.50 --segundos 8
```

---

## Ejecutar automáticamente al iniciar Windows

1. Crea un archivo `.bat`:
```bat
@echo off
pythonw C:\ruta\a\2_vigilancia.py --silencio
```

2. Presiona `Win + R`, escribe `shell:startup` y coloca el `.bat` allí.

---

## Ajuste de tolerancia

| Tolerancia | Comportamiento                              |
|------------|---------------------------------------------|
| `0.45`     | Muy estricto — puede rechazarte con poca luz|
| `0.55`     | Equilibrado — recomendado para empezar      |
| `0.65`     | Más permisivo — mayor riesgo de falsos OK   |

---

## Registro de eventos
Cada bloqueo se registra en `face_lock.log` con fecha y hora.

---

## Limitaciones conocidas
- Rendimiento reducido con poca luz (añade una lámpara de escritorio)
- No funciona con fotos impresas solo si usas el modelo `cnn` (más seguro pero más lento)
- Para máxima seguridad cambia `model="hog"` por `model="cnn"` en `2_vigilancia.py`
