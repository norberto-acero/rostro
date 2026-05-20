#%%
"""
PASO 2: Vigilancia y bloqueo automático
========================================
Monitorea la cámara continuamente. Solo bloquea el PC
cuando detecte un rostro que NO sea el tuyo.

Al bloquear, guarda una foto del intruso en la carpeta
'intrusos/' con fecha y hora.

Uso:
    python 2_vigilancia.py [--tolerancia 0.55] [--segundos 5] [--silencio]

Parámetros:
    --tolerancia   Umbral de similitud (0.0-1.0). Menor = más estricto. Recomendado: 0.50-0.60
    --segundos     Segundos con rostro desconocido antes de bloquear (default: 5)
    --silencio     No mostrar ventana de cámara (modo en segundo plano)
"""

import cv2
import face_recognition
import pickle
import time
import subprocess
import ctypes
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

PERFIL_PATH = "mi_rostro.pkl"
LOG_PATH    = "face_lock.log"
FOTOS_DIR   = Path("intrusos")

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ─── Captura de foto del intruso ──────────────────────────────────────────────

def guardar_foto_intruso(frame):
    """Guarda el frame actual en la carpeta 'intrusos/' con timestamp."""
    FOTOS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ruta = FOTOS_DIR / f"intruso_{timestamp}.jpg"
    exito = cv2.imwrite(str(ruta), frame)
    if exito:
        log.warning(f"📸 Foto del intruso guardada: {ruta}")
    else:
        log.error(f"No se pudo guardar la foto en: {ruta}")
    return ruta if exito else None


# ─── Bloqueo de pantalla (Windows) ────────────────────────────────────────────

def bloquear_pc(frame):
    """Guarda foto del intruso y luego bloquea la pantalla."""
    guardar_foto_intruso(frame)
    log.warning("🔒 BLOQUEANDO PC - rostro no autorizado detectado")
    try:
        ctypes.windll.user32.LockWorkStation()
    except Exception:
        try:
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True)
        except Exception as e:
            log.error(f"No se pudo bloquear el PC: {e}")


# ─── Carga del perfil ─────────────────────────────────────────────────────────

def cargar_perfil(ruta: str):
    if not Path(ruta).exists():
        log.error(f"Perfil no encontrado: '{ruta}'")
        log.error("Ejecuta primero '1_registrar_rostro.py'")
        sys.exit(1)
    with open(ruta, "rb") as f:
        codificacion = pickle.load(f)
    log.info(f"Perfil cargado desde '{ruta}'")
    return codificacion


# ─── Bucle principal de vigilancia ────────────────────────────────────────────

def vigilar(tolerancia: float, segundos_limite: int, silencioso: bool):
    mi_codificacion = cargar_perfil(PERFIL_PATH)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        log.error("No se pudo abrir la cámara.")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 15)

    log.info(f"Vigilancia activa | tolerancia={tolerancia} | limite={segundos_limite}s")
    log.info("MODO: bloquea SOLO cuando detecta un rostro no reconocido.")
    log.info(f"Fotos de intrusos guardadas en: {FOTOS_DIR.resolve()}")
    log.info("Presiona 'q' en la ventana para salir.")

    tiempo_intruso     = 0.0
    ultimo_frame       = time.time()
    bloqueado_rec      = False   # evita bloqueos repetidos en el mismo evento
    ultimo_frame_orig  = None    # frame sin dibujos para guardar foto limpia

    INTERVALO_FRAMES = 3
    contador_frames  = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        contador_frames += 1
        ahora  = time.time()
        delta  = ahora - ultimo_frame
        ultimo_frame = ahora

        # Guardar copia limpia del frame (sin anotaciones) para la foto
        frame_limpio = frame.copy()

        # Mostrar frames intermedios sin procesar (ahorra CPU)
        if contador_frames % INTERVALO_FRAMES != 0:
            if not silencioso:
                cv2.imshow("Face Lock - q para salir", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            continue

        # ── Detección de rostros ───────────────────────────────────────────
        pequeno = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb     = cv2.cvtColor(pequeno, cv2.COLOR_BGR2RGB)

        ubicaciones   = face_recognition.face_locations(rgb, model="hog")
        codificaciones = face_recognition.face_encodings(rgb, ubicaciones)

        yo_presente      = False
        intruso_detectado = False

        for (ubicacion, codif_encontrada) in zip(ubicaciones, codificaciones):
            distancia  = face_recognition.face_distance([mi_codificacion], codif_encontrada)[0]
            reconocido = distancia <= tolerancia

            if reconocido:
                yo_presente = True
            else:
                intruso_detectado = True

            if not silencioso:
                top, right, bottom, left = [v * 2 for v in ubicacion]
                color   = (0, 200, 0) if reconocido else (0, 50, 220)
                etiqueta = f"{'Autorizado' if reconocido else 'No autorizado'} ({1 - distancia:.0%})"
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, etiqueta, (left, top - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        # ── Lógica de estados ──────────────────────────────────────────────
        #   1. Yo presente          → reiniciar todo
        #   2. Rostro desconocido   → acumular tiempo, puede bloquear
        #   3. Sin ningún rostro    → pausar contador
        if yo_presente:
            tiempo_intruso = 0.0
            bloqueado_rec  = False

        elif intruso_detectado:
            tiempo_intruso += delta * INTERVALO_FRAMES
            # Guardar el frame limpio más reciente con intruso (mejor calidad)
            ultimo_frame_orig = frame_limpio

        # ── Estado en pantalla ─────────────────────────────────────────────
        if not silencioso:
            if yo_presente:
                estado      = "Autorizado"
                color_estado = (0, 200, 0)
            elif intruso_detectado:
                estado      = f"Rostro no reconocido: {tiempo_intruso:.1f}s / {segundos_limite}s"
                color_estado = (0, 50, 220)
            else:
                estado      = "Sin rostro detectado - en espera"
                color_estado = (160, 160, 160)

            cv2.putText(frame, estado, (10, frame.shape[0] - 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_estado, 2)
            cv2.imshow("Face Lock - q para salir", frame)

        # ── Disparar bloqueo + foto ────────────────────────────────────────
        if intruso_detectado and tiempo_intruso >= segundos_limite and not bloqueado_rec:
            # Usar el frame limpio (sin anotaciones) para la foto
            foto_frame = ultimo_frame_orig if ultimo_frame_orig is not None else frame_limpio
            bloquear_pc(foto_frame)
            bloqueado_rec  = True
            tiempo_intruso = 0.0

        # ── Salida ─────────────────────────────────────────────────────────
        if not silencioso:
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()
    log.info("Vigilancia detenida.")


# ─── Entrada ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Bloqueo automatico por reconocimiento facial")
    parser.add_argument("--tolerancia", type=float, default=0.55,
                        help="Umbral de similitud (0.0-1.0). Default: 0.55")
    parser.add_argument("--segundos", type=int, default=5,
                        help="Segundos con rostro desconocido antes de bloquear. Default: 5")
    parser.add_argument("--silencio", action="store_true",
                        help="Ejecutar sin ventana visible (modo fondo)")

    # parse_known_args ignora argumentos internos de Jupyter/IPython
    args, _ = parser.parse_known_args()

    log.info("=" * 50)
    log.info("  Face Lock iniciado")
    log.info(f"  Tolerancia: {args.tolerancia} | Limite: {args.segundos}s")
    log.info("=" * 50)

    vigilar(
        tolerancia=args.tolerancia,
        segundos_limite=args.segundos,
        silencioso=args.silencio,
    )


if __name__ == "__main__":
    main()