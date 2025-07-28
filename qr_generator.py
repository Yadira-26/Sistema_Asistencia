import qrcode
import os

def generate_qr_code(data, employee_id, save_dir="./static/qr_codes"):
    """
    Genera un código QR y lo guarda como una imagen.
    :param data: Los datos a codificar en el QR (ej. ID del empleado).
    :param employee_id: ID del empleado para nombrar el archivo.
    :param save_dir: Directorio donde se guardarán los códigos QR.
    :return: La ruta relativa del archivo QR guardado.
    """
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    filename = f"qr_{employee_id}.png"
    filepath = os.path.join(save_dir, filename)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(filepath)
    
    # Asegurar que la ruta sea compatible con web (solo /)
    return os.path.join(os.path.basename(save_dir), filename).replace('\\', '/')

if __name__ == '__main__':
    # Ejemplo de uso
    employee_data = "EMP001"
    qr_path = generate_qr_code(employee_data, "EMP001")
    print(f"Código QR para {employee_data} generado en: {qr_path}")