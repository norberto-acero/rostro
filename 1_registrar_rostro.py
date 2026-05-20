"""
PASO 1: Registrar tu rostro
===========================
Ejecuta este script UNA sola vez para capturar y guardar
la codificación de tu rostro.

Requisitos:
    pip install face_recognition opencv-python numpy

Nota: face_recognition requiere dlib, que en Windows
necesita CMake y Visual C++ Build Tools instalados.
Alternativa más fácil: instalar con conda o usar la
rueda precompilada (ver README).
"""

import cv2
import face_recognition
import numpy as np
import pickle
import os
import sys

PERFIL_PATH = "mi_rostro.pkl"
NUM_MUESTRAS = 30  # cuántos frames capturar para promediar


def registrar():
    print("=" * 50)
    print("  Registro de rostro para bloqueo automático")
    print("=" * 50)
    print(f"\nSe capturarán {NUM_MUESTRAS} muestras de tu rostro.")
    print("Mira directamente a la cámara y mantén el rostro centrado.\n")

    if os.path.exists(PERFIL_PATH):
        resp = input(f"Ya existe un perfil guardado ({PERFIL_PATH}). ¿Sobreescribir? [s/N]: ")
        if resp.lower() != "s":
            print("Cancelado.")
            sys.exit(0)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: No se pudo abrir la cámara.")
        sys.exit(1)

    codificaciones = []
    muestras_tomadas = 0

    print("Presiona 'q' para cancelar en cualquier momento.\n")

    while muestras_tomadas < NUM_MUESTRAS:
        ret, frame = cap.read()
        if not ret:
            continue

        # Reducir resolución para mayor velocidad
        pequeño = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb = cv2.cvtColor(pequeño, cv2.COLOR_BGR2RGB)

        ubicaciones = face_recognition.face_locations(rgb, model="hog")
        codifs = face_recognition.face_encodings(rgb, ubicaciones)

        # Solo procesar si hay exactamente un rostro
        if len(codifs) == 1:
            codificaciones.append(codifs[0])
            muestras_tomadas += 1

            # Dibujar rectángulo verde alrededor del rostro
            top, right, bottom, left = ubicaciones[0]
            # Escalar de vuelta a tamaño original
            top, right, bottom, left = top * 2, right * 2, bottom * 2, left * 2
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 200, 0), 2)

            progreso = int((muestras_tomadas / NUM_MUESTRAS) * 30)
            barra = f"[{'█' * progreso}{'░' * (30 - progreso)}] {muestras_tomadas}/{NUM_MUESTRAS}"
            cv2.putText(frame, barra, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)
        elif len(codifs) == 0:
            cv2.putText(frame, "No se detecta rostro", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 100, 255), 2)
        else:
            cv2.putText(frame, "Detectados varios rostros - usa solo uno", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 100, 255), 2)

        cv2.imshow("Registro de rostro - ESC para cancelar", frame)

        tecla = cv2.waitKey(1) & 0xFF
        if tecla == 27 or tecla == ord("q"):  # ESC o q
            print("\nCancelado por el usuario.")
            cap.release()
            cv2.destroyAllWindows()
            sys.exit(0)

    cap.release()
    cv2.destroyAllWindows()

    # Calcular codificación promedio (más robusta que una sola muestra)
    codificacion_media = np.mean(codificaciones, axis=0)

    with open(PERFIL_PATH, "wb") as f:
        pickle.dump(codificacion_media, f)

    print(f"\n✓ Rostro registrado exitosamente en '{PERFIL_PATH}'")
    print("  Ahora puedes ejecutar '2_vigilancia.py' para activar el bloqueo automático.")


if __name__ == "__main__":
    registrar()
