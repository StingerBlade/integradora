from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.hashers import check_password
import json
from .models import user_collection
import uuid

@csrf_exempt
@require_http_methods(["POST"])
def mobile_login(request):
    """
    API endpoint para login desde la aplicación móvil

    Espera un JSON con el siguiente formato:
    {
        "usuario": "nombre_usuario",
        "password": "contraseña"
    }

    Retorna información del usuario y un token de sesión si las credenciales son correctas
    """
    try:
        # Decodificar el cuerpo JSON
        data = json.loads(request.body)

        # Validar campos requeridos
        if 'usuario' not in data or 'password' not in data:
            return JsonResponse({
                'success': False,
                'error': 'Se requieren usuario y contraseña'
            }, status=400)

        # Obtener credenciales
        username = data.get('usuario')
        password = data.get('password')

        # Buscar usuario en la base de datos
        user = user_collection.find_one({"usuario": username})

        # Verificar si el usuario existe
        if not user:
            return JsonResponse({
                'success': False,
                'error': 'Usuario no encontrado'
            }, status=404)

        # Verificar si el usuario está activo
        if not user.get('activo', True):
            return JsonResponse({
                'success': False,
                'error': 'Esta cuenta ha sido desactivada'
            }, status=403)

        # Verificar contraseña
        if not check_password(password, user['contrasena']):
            return JsonResponse({
                'success': False,
                'error': 'Contraseña incorrecta'
            }, status=401)

        # Crear respuesta con datos del usuario (excluyendo información sensible)
        user_data = {
            'usuario': user['usuario'],
            'email': user['email'],
            # Puedes agregar más campos según necesites
        }

        # Generar un ID de sesión simple (en producción deberías usar JWT u otra solución más segura)
        session_id = str(uuid.uuid4())

        return JsonResponse({
            'success': True,
            'message': 'Login exitoso',
            'user': user_data,
            'session_token': session_id
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Formato JSON inválido'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)