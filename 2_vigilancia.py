#%%
"""
PASO 2: Vigilancia y bloqueo automático
========================================
Monitorea la cámara continuamente. Si no se detecta
tu rostro durante N segundos consecutivos, bloquea el PC.

Ejecútalo en segundo plano o al inicio de sesión de Windows.

Uso:
    python 2_vigilancia.py [--tolerancia 0.55] [--segundos 5] [--silencio]

Parámetros:
    --tolerancia   Umbral de similitud (0.0-1.0). Menor = más estricto. Recomendado: 0.50-0.60
    --segundos     Segundos sin reconocerte antes de bloquear (default: 5)
    --silencio     No mostrar ventana de cámara (modo en segundo plano)
"""

import cv2
import face_recognition
import pickle
import time
import subprocess
import ctypes
import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

PERFIL_PATH = "mi_rostro.pkl"
LOG_PATH = "face_lock.log"

# ─── Configuración de logging ────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ─── Función de bloqueo (Windows) ────────────────────────────────────────────

def bloquear_pc():
    """Bloquea la pantalla en Windows usando la API nativa."""
    log.warning("🔒 BLOQUEANDO PC - rostro no autorizado detectado")
    try:
        # Método 1: API de Windows (más confiable)
        ctypes.windll.user32.LockWorkStation()
    except Exception:
        # Método 2: Fallback via rundll32
        try:
            subprocess.run(
                ["rundll32.exe", "user32.dll,LockWorkStation"],
                check=True
            )
        except Exception as e:
            log.error(f"No se pudo bloquear el PC: {e}")


# ─── Carga del perfil guardado ────────────────────────────────────────────────

def cargar_perfil(ruta: str):
    if not Path(ruta).exists():
        log.error(f"Perfil no encontrado: '{ruta}'")
        log.error("Ejecuta primero '1_registrar_rostro.py'")
        sys.exit(1)
    with open(ruta, "rb") as f:
        codificacion = pickle.load(f)
    log.info(f"Perfil cargado correctamente desde '{ruta}'")
    return codificacion


# ─── Bucle principal de vigilancia ───────────────────────────────────────────

def vigilar(tolerancia: float, segundos_limite: int, silencioso: bool):
    mi_codificacion = cargar_perfil(PERFIL_PATH)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        log.error("No se pudo abrir la cámara.")
        sys.exit(1)

    # Ajustes de captura para mayor rendimiento
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 15)

    log.info(f"Vigilancia activa | tolerancia={tolerancia} | límite={segundos_limite}s")
    log.info("Presiona 'q' en la ventana de cámara para salir.")

    tiempo_sin_reconocer = 0.0
    ultimo_frame = time.time()
    bloqueado_recientemente = False

    # Procesar 1 de cada N frames para ahorrar CPU
    INTERVALO_FRAMES = 3
    contador_frames = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        contador_frames += 1
        ahora = time.time()
        delta = ahora - ultimo_frame
        ultimo_frame = ahora

        # ── Procesar cada INTERVALO_FRAMES frames ──────────────────────────
        if contador_frames % INTERVALO_FRAMES != 0:
            if not silencioso:
                cv2.imshow("Face Lock - q para salir", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            continue

        # Redimensionar para mayor velocidad
        pequeño = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb = cv2.cvtColor(pequeño, cv2.COLOR_BGR2RGB)

        ubicaciones = face_recognition.face_locations(rgb, model="hog")
        codificaciones = face_recognition.face_encodings(rgb, ubicaciones)

        yo_presente = False

        for (ubicacion, codif_encontrada) in zip(ubicaciones, codificaciones):
            distancia = face_recognition.face_distance([mi_codificacion], codif_encontrada)[0]
            reconocido = distancia <= tolerancia

            if reconocido:
                yo_presente = True

            if not silencioso:
                # Escalar coordenadas
                top, right, bottom, left = [v * 2 for v in ubicacion]
                color = (0, 200, 0) if reconocido else (0, 50, 220)
                etiqueta = f"{'Autorizado' if reconocido else 'No autorizado'} ({1 - distancia:.0%})"
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, etiqueta, (left, top - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        # ── Conteo de tiempo sin reconocerte ──────────────────────────────
        if yo_presente:
            tiempo_sin_reconocer = 0.0
            bloqueado_recientemente = False
        else:
            tiempo_sin_reconocer += delta * INTERVALO_FRAMES

        # ── Mostrar estado en pantalla ─────────────────────────────────────
        if not silencioso:
            restante = max(0, segundos_limite - tiempo_sin_reconocer)
            estado = f"{'OK' if yo_presente else f'Sin reconocer: {tiempo_sin_reconocer:.1f}s / {segundos_limite}s'}"
            color_estado = (0, 200, 0) if yo_presente else (0, 100, 255)
            cv2.putText(frame, estado, (10, frame.shape[0] - 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_estado, 2)
            cv2.imshow("Face Lock - q para salir", frame)

        # ── Disparar bloqueo ───────────────────────────────────────────────
        if tiempo_sin_reconocer >= segundos_limite and not bloqueado_recientemente:
            bloquear_pc()
            bloqueado_recientemente = True
            tiempo_sin_reconocer = 0.0  # reiniciar contador tras bloquear

        # ── Salida ─────────────────────────────────────────────────────────
        if not silencioso:
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()
    log.info("Vigilancia detenida.")


# ─── Entrada ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Bloqueo automático por reconocimiento facial")
    parser.add_argument("--tolerancia", type=float, default=0.55,
                        help="Umbral de similitud (0.0-1.0). Default: 0.55")
    parser.add_argument("--segundos", type=int, default=5,
                        help="Segundos sin reconocerte antes de bloquear. Default: 5")
    parser.add_argument("--silencio", action="store_true",
                        help="Ejecutar sin ventana visible (modo fondo)")

    # parse_known_args ignora argumentos desconocidos de Jupyter/IPython
    # en lugar de lanzar un error al encontrar --f=kernel-xxx.json
    args, _ = parser.parse_known_args()

    log.info("━" * 50)
    log.info("  Face Lock iniciado")
    log.info(f"  Tolerancia: {args.tolerancia} | Límite: {args.segundos}s")
    log.info("━" * 50)

    vigilar(
        tolerancia=args.tolerancia,
        segundos_limite=args.segundos,
        silencioso=args.silencio,
    )


if __name__ == "__main__":
    main()