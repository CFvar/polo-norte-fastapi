class AppError(Exception):
    """Error de dominio/HTTP. El manejador global lo convierte al formato estándar:
    { codigo, mensaje, detalles, timestamp, ruta }
    """

    def __init__(self, status: int, codigo: str, mensaje: str, detalles: list[str] | None = None):
        super().__init__(mensaje)
        self.status = status
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalles = detalles or []
