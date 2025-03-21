from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from bson.objectid import ObjectId
import json
from datetime import datetime, timezone
import pytz
from .models import user_collection, escritorio_collection
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
@csrf_exempt
@require_http_methods(["POST"])
def register_timer(request):
    """
    API endpoint para recibir datos del ESP32

    Espera un JSON con el siguiente formato:
    {
        "usuario": "nombre_usuario",
        "seconds": 3600,
        "escritorio_serie": "123456",
        "apiKey": "clave_secreta",
        "modo": "estudio"  # o "entretenimiento"
    }

    La fecha/hora se registra automáticamente en el servidor
    """
    try:
        # Decodificar el cuerpo JSON
        data = json.loads(request.body)

        # Validar campos requeridos
        required_fields = ['usuario', 'seconds', 'escritorio_serie', 'apiKey', 'modo']
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'success': False,
                    'error': f'Campo requerido ausente: {field}'
                }, status=400)

        # Verificar la API key (implementar una validación más segura en producción)
        api_key = data.get('apiKey')
        if api_key != 'esp32_secret_key':  # Ejemplo simplificado - usar un método más seguro en producción
            return JsonResponse({
                'success': False,
                'error': 'API key inválida'
            }, status=401)

        # Verificar si el usuario existe
        username = data.get('usuario')
        user = user_collection.find_one({"usuario": username})
        if not user:
            return JsonResponse({
                'success': False,
                'error': 'Usuario no encontrado'
            }, status=404)

        # Verificar si el modo es válido
        modo = data.get('modo')
        if modo not in ['estudio', 'entretenimiento']:
            return JsonResponse({
                'success': False,
                'error': 'Modo inválido. Debe ser "estudio" o "entretenimiento"'
            }, status=400)

        # Verificar si el escritorio existe
        escritorio_serie = data.get('escritorio_serie')
        escritorio = escritorio_collection.find_one({"numero_serie": escritorio_serie})
        if not escritorio:
            return JsonResponse({
                'success': False,
                'error': 'Escritorio no encontrado'
            }, status=404)

        # Verificar si el usuario está vinculado al escritorio
        if username not in escritorio.get('usuarios', []):
            return JsonResponse({
                'success': False,
                'error': 'Usuario no vinculado a este escritorio'
            }, status=403)

        # Zona horaria del norte de México
        local_timezone = pytz.timezone('America/Monterrey')

        # Obtener tiempos en UTC y tiempo local
        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(local_timezone)

        # Crear el registro del temporizador
        timer_data = {
            'seconds': data.get('seconds'),
            'escritorio_id': str(escritorio['_id']),
            'escritorio_serie': escritorio_serie,
            'escritorio_nombre': escritorio.get('nombre', 'Sin nombre'),
            'timestamp': now_utc,
            'fecha_str': now_local.strftime('%Y-%m-%d %H:%M:%S')
        }

        # Actualizar el documento del usuario agregando el temporizador al modo específico
        update_result = user_collection.update_one(
            {"usuario": username},
            {"$push": {f"modos.{modo}": timer_data}}
        )

        # Si la actualización fue exitosa, enviar notificación por WebSocket
        if update_result.modified_count > 0:
            try:
                # Obtener capa de canales para WebSockets
                channel_layer = get_channel_layer()

                # Enviar mensaje al grupo del usuario
                async_to_sync(channel_layer.group_send)(
                    f'user_{username}',
                    {
                        'type': 'usage_update',
                        'message': {
                            'mode': modo,
                            'seconds': data.get('seconds'),
                            'escritorio_nombre': escritorio.get('nombre', 'Sin nombre'),
                            'timestamp': now_local.strftime('%Y-%m-%d %H:%M:%S')
                        }
                    }
                )
                print(f"WebSocket notification sent to user_{username}")
            except Exception as ws_error:
                print(f"WebSocket error: {str(ws_error)}")
                # Continuar incluso si hay un error en WebSocket
                pass

            return JsonResponse({
                'success': True,
                'message': f'Datos del temporizador registrados correctamente en modo {modo}',
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No se pudo actualizar el usuario'
            }, status=500)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
# Este metodo casi no se usa si no es que nunca
@require_http_methods(["GET"])
def get_user_timers(request, username, modo=None):
    """
    Obtiene todos los temporizadores registrados para un usuario específico,
    opcionalmente filtrados por modo
    """
    try:
        # Verificar si el usuario existe
        user = user_collection.find_one({"usuario": username})
        if not user:
            return JsonResponse({
                'success': False,
                'error': 'Usuario no encontrado'
            }, status=404)

        # Verificar si el usuario actual tiene permiso (sesión)
        if request.session.get('usuario') != username and request.session.get('tipo_usuario') != 'admin':
            return JsonResponse({
                'success': False,
                'error': 'No tienes permiso para ver estos datos'
            }, status=403)

        # Obtener los datos de los temporizadores
        modos = user.get('modos', {})

        result = {}

        if modo:
            # Si se especifica un modo, devolver solo ese modo
            if modo in modos:
                result[modo] = modos[modo]
            else:
                result[modo] = []
        else:
            # De lo contrario, devolver todos los modos
            result = modos

        return JsonResponse({
            'success': True,
            'timers': result
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)