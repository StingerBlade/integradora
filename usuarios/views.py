from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from .models import user_collection, admin_collection, escritorio_collection
from django.contrib.auth.hashers import make_password, check_password
from functools import wraps
from django.views.decorators.csrf import csrf_exempt
import json
from bson.objectid import ObjectId
import random
from datetime import datetime, timedelta
import calendar

# Decorador para verificar la sesión
def session_required(view_func):
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if 'usuario' not in request.session:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapped_view

# Rutas
def error_404(request, exception):
    return render(request, '404.html', status=404)

def index(request):
    return render(request, 'index.html')

def register(request):
    return render(request, 'register.html')

# Registro de usuarios
@require_http_methods(["POST"])
def mregister(request):
    usuario = request.POST.get('username')
    password = request.POST.get('password1')
    password2 = request.POST.get('password2')
    email = request.POST.get('email')

    if password != password2:
        return render(request, 'register.html', {'error': 'Las contraseñas no coinciden'})

    if user_collection.find_one({"usuario": usuario}):
        return render(request, 'register.html', {'error': 'El usuario ya existe'})

    hash_password = make_password(password)
    modos_iniciales = {
        'estudio': [],
        'entretenimiento': [],
    }

    user_collection.insert_one({
        "usuario": usuario,
        "contrasena": hash_password,
        "email": email,
        "modos": modos_iniciales,
        "activo": True  #madre pa que no borre totalmente solo los desactive
    })

    return redirect('login')

def login(request):
    return render(request, 'login.html')

# Login de usuarios
@require_http_methods(["POST"])
def mlogin(request):
    usuario = request.POST.get('username')
    password = request.POST.get('password')

    # Buscar en ambas colecciones
    user = user_collection.find_one({"usuario": usuario})
    admin = admin_collection.find_one({"usuario": usuario})

    if user and admin:
        return render(request, 'login.html', {'error': 'Conflicto: El usuario existe en ambas colecciones'})

    # Determinar si es usuario o admin
    if user and check_password(password, user['contrasena']):
        # Verificar si el usuario está activo
        if not user.get('activo', True):
            return render(request, 'login.html', {'error': 'Esta cuenta ha sido desactivada. Contacte al administrador.'})

        request.session['usuario'] = usuario
        request.session['email'] = user['email']
        request.session['tipo_usuario'] = 'usuario'
    elif admin and check_password(password, admin['contrasena']):
        request.session['usuario'] = usuario
        request.session['email'] = admin['email']
        request.session['tipo_usuario'] = 'admin'
    else:
        return render(request, 'login.html', {'error': 'Usuario o contraseña incorrectos'})

    request.session.modified = True
    return redirect('dashboard')

@session_required
def dashboard(request):
    usuario = request.session.get('usuario', 'Invitado')
    tipo_usuario = request.session.get('tipo_usuario', 'usuario')

    # Buscar en ambas colecciones
    user = user_collection.find_one({"usuario": usuario})
    admin = admin_collection.find_one({"usuario": usuario})

    if user and admin:
        return JsonResponse({'error': 'Conflicto: El usuario existe en ambas colecciones'}, status=500)

    if not user and not admin:
        return redirect('login')

    # Determinar tipo de usuario y email
    if user:
        email = user.get('email', 'No disponible')
    else:
        email = admin.get('email', 'No disponible')

    # Datos específicos según el tipo de usuario
    if tipo_usuario == 'admin':
        # Para administradores: lista de usuarios
        usuarios = list(user_collection.find({}, {"_id": 0, "usuario": 1, "email": 1, "modos": 1, "activo": 1}))

        # Convertir valores explícitamente para evitar problemas con BSON
        for user in usuarios:
            if 'activo' not in user:
                user['activo'] = True

        # No necesitamos escritorios para admins en el dashboard principal
        escritorios = []
        week_data = None
    else:
        # Para usuarios normales: sus escritorios
        usuarios = None

        # Obtener escritorios asociados al usuario
        escritorios_cursor = escritorio_collection.find({
            "usuarios": usuario,
            "activo": True
        })

        escritorios = []
        for escritorio in escritorios_cursor:
            # Convertir _id a string
            escritorio['id'] = str(escritorio['_id'])
            escritorios.append(escritorio)

        # Preparar datos del calendario con tiempo total por día
        import datetime
        from datetime import timedelta

        # Obtener fecha actual y calcular inicio de la semana (lunes)
        today = datetime.datetime.now()
        start_of_week = today - timedelta(days=today.weekday())

        # Preparar datos para cada día de la semana
        week_data = []
        day_names = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

        for i in range(7):
            current_date = start_of_week + timedelta(days=i)
            date_str = current_date.strftime('%d/%m')

            # Inicializar tiempo total para este día
            total_seconds = 0

            # Si tenemos datos de usuario, buscar actividad en este día
            if user and 'modos' in user:
                # Formato de fecha para comparar
                target_date = current_date.strftime('%Y-%m-%d')

                # Buscar en modo estudio
                for entry in user['modos'].get('estudio', []):
                    if 'fecha_str' in entry and entry['fecha_str'].startswith(target_date):
                        total_seconds += entry.get('seconds', 0)

                # Buscar en modo entretenimiento
                for entry in user['modos'].get('entretenimiento', []):
                    if 'fecha_str' in entry and entry['fecha_str'].startswith(target_date):
                        total_seconds += entry.get('seconds', 0)

            # Convertir segundos a formato legible
            if total_seconds > 0:
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            else:
                time_str = "0m"

            # Determinar si es el día actual comparando día, mes y año
            is_current = (current_date.day == today.day and
                          current_date.month == today.month and
                          current_date.year == today.year)

            week_data.append({
                'name': day_names[i],
                'date': date_str,
                'time': time_str,
                'is_current': is_current
            })

    # Mostrar mensaje de éxito si existe
    message = request.session.pop('message', None)

    return render(request, 'dashboard.html', {
        'usuario': usuario,
        'email': email,
        'tipo_usuario': tipo_usuario,
        'usuarios': usuarios,
        'escritorios': escritorios,
        'week_data': week_data,
        'message': message
    })
# CRUD para usuarios
@session_required
@require_http_methods(["POST"])
def edit_user(request):
    # Verificar que el usuario actual es admin
    if request.session.get('tipo_usuario') != 'admin':
        return redirect('dashboard')

    old_usuario = request.POST.get('old_usuario')
    nuevo_usuario = request.POST.get('usuario')
    nuevo_email = request.POST.get('email')

    # Verificar que el usuario existe
    user = user_collection.find_one({"usuario": old_usuario})
    if not user:
        request.session['message'] = {'type': 'error', 'text': 'Usuario no encontrado'}
        return redirect('dashboard')

    # Verificar si el nuevo nombre de usuario ya existe (si está cambiando)
    if old_usuario != nuevo_usuario and user_collection.find_one({"usuario": nuevo_usuario}):
        request.session['message'] = {'type': 'error', 'text': 'El nombre de usuario ya está en uso'}
        return redirect('dashboard')

    # Actualizar usuario y email
    update_result = user_collection.update_one(
        {"usuario": old_usuario},
        {"$set": {
            "usuario": nuevo_usuario,
            "email": nuevo_email
        }}
    )

    if update_result.modified_count > 0:
        request.session['message'] = {'type': 'success', 'text': 'Usuario actualizado correctamente'}
    else:
        request.session['message'] = {'type': 'info', 'text': 'No se realizaron cambios'}

    return redirect('dashboard')

# Función para desactivar usuarios (soft delete)
@session_required
@require_http_methods(["POST"])
def deactivate_user(request):
    # Verificar que el usuario actual es admin
    if request.session.get('tipo_usuario') != 'admin':
        return redirect('dashboard')

    usuario_a_desactivar = request.POST.get('usuario')

    # Verificar que el usuario existe
    user = user_collection.find_one({"usuario": usuario_a_desactivar})
    if not user:
        request.session['message'] = {'type': 'error', 'text': 'Usuario no encontrado'}
        return redirect('dashboard')

    # Desactivar el usuario cambiando su estado a False
    update_result = user_collection.update_one(
        {"usuario": usuario_a_desactivar},
        {"$set": {"activo": False}}
    )

    if update_result.modified_count > 0:
        request.session['message'] = {'type': 'success', 'text': f'Usuario {usuario_a_desactivar} desactivado correctamente'}
    else:
        request.session['message'] = {'type': 'error', 'text': 'No se pudo desactivar el usuario'}

    return redirect('dashboard')

# Función para reactivar usuarios
@session_required
@require_http_methods(["POST"])
def reactivate_user(request):
    # Verificar que el usuario actual es admin
    if request.session.get('tipo_usuario') != 'admin':
        return redirect('dashboard')

    usuario_a_reactivar = request.POST.get('usuario')

    # Verificar que el usuario existe
    user = user_collection.find_one({"usuario": usuario_a_reactivar})
    if not user:
        request.session['message'] = {'type': 'error', 'text': 'Usuario no encontrado'}
        return redirect('dashboard')

    # Reactivar el usuario cambiando su estado a True
    update_result = user_collection.update_one(
        {"usuario": usuario_a_reactivar},
        {"$set": {"activo": True}}
    )

    if update_result.modified_count > 0:
        request.session['message'] = {'type': 'success', 'text': f'Usuario {usuario_a_reactivar} reactivado correctamente'}
    else:
        request.session['message'] = {'type': 'error', 'text': 'No se pudo reactivar el usuario'}

    return redirect('dashboard')

# FUNCIONES PARA ESCRITORIOS
# Administración de escritorios (admin)
@session_required
def admin_escritorios(request):
    # Verificar que el usuario actual es admin
    if request.session.get('tipo_usuario') != 'admin':
        return redirect('dashboard')

    escritorios_cursor = escritorio_collection.find()
    escritorios = []
    for escritorio in escritorios_cursor:
        # Convertir _id a string
        escritorio['id'] = str(escritorio['_id'])
        escritorios.append(escritorio)

    return render(request, 'admin_escritorios.html', {
        'escritorios': escritorios,
        'message': request.session.pop('message', None)
    })


# Crear un nuevo escritorio
@session_required
@require_http_methods(["POST"])
def crear_escritorio(request):
    # Verificar que el usuario actual es admin
    if request.session.get('tipo_usuario') != 'admin':
        return redirect('dashboard')

    numero_serie = request.POST.get('numero_serie')  # Número de chip del ESP32
    nombre = request.POST.get('nombre', '')  # Opcional, puede estar vacío
    descripcion = request.POST.get('descripcion', '')  # Opcional, puede estar vacío

    # Solo verificamos que el número de serie esté presente
    if not numero_serie:
        request.session['message'] = {'type': 'error', 'text': 'El número de chip del ESP32 es obligatorio'}
        return redirect('admin_escritorios')

    # Si el nombre está vacío, usamos un nombre predeterminado basado en el número de serie
    if not nombre:
        nombre = f"Escritorio {numero_serie[-4:]}"  # Últimos 4 caracteres del número de chip

    # Verificar que el número de serie no exista ya
    if escritorio_collection.find_one({"numero_serie": numero_serie}):
        request.session['message'] = {'type': 'error', 'text': 'Ya existe un escritorio con este número de chip'}
        return redirect('admin_escritorios')

    # Crear el escritorio
    nuevo_escritorio = {
        "nombre": nombre,
        "descripcion": descripcion,
        "usuarios": [],
        "activo": True,
        "numero_serie": numero_serie
    }

    escritorio_collection.insert_one(nuevo_escritorio)

    request.session['message'] = {'type': 'success', 'text': f'Escritorio creado correctamente con número de chip: {numero_serie}'}
    return redirect('admin_escritorios')

# Desactivar un escritorio (soft delete)
@session_required
@require_http_methods(["POST"])
def desactivar_escritorio(request):
    # Verificar que el usuario actual es admin
    if request.session.get('tipo_usuario') != 'admin':
        return redirect('dashboard')

    escritorio_id = request.POST.get('escritorio_id')

    if not escritorio_id:
        request.session['message'] = {'type': 'error', 'text': 'ID de escritorio no proporcionado'}
        return redirect('admin_escritorios')

    try:
        id_obj = ObjectId(escritorio_id)
    except:
        request.session['message'] = {'type': 'error', 'text': 'ID de escritorio inválido'}
        return redirect('admin_escritorios')

    update_result = escritorio_collection.update_one(
        {"_id": id_obj},
        {"$set": {"activo": False}}
    )

    if update_result.modified_count > 0:
        request.session['message'] = {'type': 'success', 'text': 'Escritorio desactivado correctamente'}
    else:
        request.session['message'] = {'type': 'error', 'text': 'No se pudo desactivar el escritorio'}

    return redirect('admin_escritorios')

# Reactivar un escritorio
@session_required
@require_http_methods(["POST"])
def reactivar_escritorio(request):
    # Verificar que el usuario actual es admin
    if request.session.get('tipo_usuario') != 'admin':
        return redirect('dashboard')

    escritorio_id = request.POST.get('escritorio_id')

    if not escritorio_id:
        request.session['message'] = {'type': 'error', 'text': 'ID de escritorio no proporcionado'}
        return redirect('admin_escritorios')

    try:
        id_obj = ObjectId(escritorio_id)
    except:
        request.session['message'] = {'type': 'error', 'text': 'ID de escritorio inválido'}
        return redirect('admin_escritorios')

    update_result = escritorio_collection.update_one(
        {"_id": id_obj},
        {"$set": {"activo": True}}
    )

    if update_result.modified_count > 0:
        request.session['message'] = {'type': 'success', 'text': 'Escritorio reactivado correctamente'}
    else:
        request.session['message'] = {'type': 'error', 'text': 'No se pudo reactivar el escritorio'}

    return redirect('admin_escritorios')

# Vista para que los usuarios ingresen el número de serie
@session_required
def vincular_escritorio(request):
    if request.session.get('tipo_usuario') != 'usuario':
        return redirect('dashboard')

    return render(request, 'vincular_escritorio.html', {
        'message': request.session.pop('message', None)
    })

# Asociar usuario a escritorio por número de serie
@session_required
@require_http_methods(["POST"])
def asociar_por_serie(request):
    if request.session.get('tipo_usuario') != 'usuario':
        return redirect('dashboard')

    usuario = request.session.get('usuario')
    numero_serie = request.POST.get('numero_serie')

    if not numero_serie:
        request.session['message'] = {'type': 'error', 'text': 'Debe ingresar el número de chip del ESP32'}
        return redirect('vincular_escritorio')

    # Buscar el escritorio por número de serie (chip)
    escritorio = escritorio_collection.find_one({
        "numero_serie": numero_serie,
        "activo": True
    })

    if not escritorio:
        request.session['message'] = {'type': 'error', 'text': 'Número de chip inválido o escritorio inactivo'}
        return redirect('vincular_escritorio')

    # Asociar usuario si no está ya asociado
    if usuario not in escritorio.get('usuarios', []):
        escritorio_collection.update_one(
            {"_id": escritorio["_id"]},
            {"$push": {"usuarios": usuario}}
        )
        request.session['message'] = {'type': 'success', 'text': f'Te has asociado al escritorio "{escritorio["nombre"]}"'}
    else:
        request.session['message'] = {'type': 'info', 'text': 'Ya estás asociado a este escritorio'}

    return redirect('mis_escritorios')

# Desasociar usuario de escritorio
@session_required
@require_http_methods(["POST"])
def desasociar_escritorio(request):
    if request.session.get('tipo_usuario') != 'usuario':
        return redirect('dashboard')

    usuario = request.session.get('usuario')
    escritorio_id = request.POST.get('escritorio_id')

    if not escritorio_id:
        request.session['message'] = {'type': 'error', 'text': 'ID de escritorio no proporcionado'}
        return redirect('mis_escritorios')

    try:
        id_obj = ObjectId(escritorio_id)
    except:
        request.session['message'] = {'type': 'error', 'text': 'ID de escritorio inválido'}
        return redirect('mis_escritorios')

    # Desasociar usuario
    update_result = escritorio_collection.update_one(
        {"_id": id_obj},
        {"$pull": {"usuarios": usuario}}
    )

    if update_result.modified_count > 0:
        request.session['message'] = {'type': 'success', 'text': 'Te has desasociado del escritorio correctamente'}
    else:
        request.session['message'] = {'type': 'error', 'text': 'No se pudo desasociar del escritorio'}

    return redirect('mis_escritorios')

# Ver mis escritorios asociados
@session_required
def mis_escritorios(request):
    if request.session.get('tipo_usuario') != 'usuario':
        return redirect('dashboard')

    usuario = request.session.get('usuario')

    # Obtener escritorios asociados al usuario
    escritorios_cursor = escritorio_collection.find({
        "usuarios": usuario,
        "activo": True
    })

    escritorios = []
    for escritorio in escritorios_cursor:
        # Convertir _id a string
        escritorio['id'] = str(escritorio['_id'])
        escritorios.append(escritorio)

    return render(request, 'mis_escritorios.html', {
        'escritorios': escritorios,
        'message': request.session.pop('message', None)
    })

# Cerrar sesión
def logout(request):
    if 'usuario' in request.session:
        del request.session['usuario']
    if 'email' in request.session:
        del request.session['email']
    if 'tipo_usuario' in request.session:
        del request.session['tipo_usuario']

    return redirect('index')

# Mantener por compatibilidad
@csrf_exempt
def update_user(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            old_usuario = data.get('oldUsuario')
            usuario = data.get('usuario')
            email = data.get('email')

            # Verificar que el usuario existe
            user = user_collection.find_one({"usuario": old_usuario})
            if not user:
                return JsonResponse({'error': 'Usuario no encontrado'}, status=404)

            # Verificar si el nuevo nombre de usuario ya existe
            if old_usuario != usuario and user_collection.find_one({"usuario": usuario}):
                return JsonResponse({'error': 'El nombre de usuario ya está en uso'}, status=400)

            # Actualizar usuario y email
            update_result = user_collection.update_one(
                {"usuario": old_usuario},
                {"$set": {
                    "usuario": usuario,
                    "email": email
                }}
            )

            if update_result.modified_count > 0:
                return JsonResponse({'message': 'Usuario actualizado correctamente'})
            else:
                return JsonResponse({'message': 'No se realizaron cambios'})

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Formato JSON inválido'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Método no permitido'}, status=405)

# Función para que los usuarios editen escritorios
@session_required
@require_http_methods(["POST"])
def editar_escritorio(request):
    if request.session.get('tipo_usuario') != 'usuario':
        return redirect('dashboard')

    usuario = request.session.get('usuario')
    escritorio_id = request.POST.get('escritorio_id')
    nuevo_nombre = request.POST.get('nombre')
    nueva_descripcion = request.POST.get('descripcion')

    if not escritorio_id:
        request.session['message'] = {'type': 'error', 'text': 'ID de escritorio no proporcionado'}
        return redirect('mis_escritorios')

    try:
        id_obj = ObjectId(escritorio_id)
    except:
        request.session['message'] = {'type': 'error', 'text': 'ID de escritorio inválido'}
        return redirect('mis_escritorios')

    # Verificar que el usuario está asociado al escritorio
    escritorio = escritorio_collection.find_one({
        "_id": id_obj,
        "usuarios": usuario,
        "activo": True
    })

    if not escritorio:
        request.session['message'] = {'type': 'error', 'text': 'No tienes acceso a este escritorio'}
        return redirect('mis_escritorios')

    # Actualizar nombre y descripción
    update_result = escritorio_collection.update_one(
        {"_id": id_obj, "usuarios": usuario},
        {"$set": {
            "nombre": nuevo_nombre,
            "descripcion": nueva_descripcion
        }}
    )

    if update_result.modified_count > 0:
        request.session['message'] = {'type': 'success', 'text': 'Escritorio actualizado correctamente'}
    else:
        request.session['message'] = {'type': 'info', 'text': 'No se realizaron cambios'}

    return redirect('mis_escritorios')

@session_required
def mis_timers(request, modo=None):
    """
    Vista para mostrar los temporizadores registrados por el ESP32 para el usuario actual
    """
    if request.session.get('tipo_usuario') != 'usuario':
        return redirect('dashboard')

    usuario = request.session.get('usuario')

    # Obtener escritorios asociados al usuario para filtros
    escritorios_cursor = escritorio_collection.find({
        "usuarios": usuario,
        "activo": True
    })

    escritorios = []
    for escritorio in escritorios_cursor:
        # Convertir _id a string
        escritorio['id'] = str(escritorio['_id'])
        escritorios.append(escritorio)

    # Obtener el usuario con sus datos de temporizador
    user = user_collection.find_one({"usuario": usuario})

    if not user:
        return redirect('login')

    # Obtener los temporizadores del modo especificado o todos
    timers = []
    modos = user.get('modos', {})

    if modo and modo in modos:
        # Solo mostrar un modo específico
        timers = modos[modo]
        modo_actual = modo
    elif modo:
        # Si se especificó un modo que no existe, devolver lista vacía
        timers = []
        modo_actual = modo
    else:
        # Mostrar todos los modos combinados y ordenados por fecha
        for m in ['estudio', 'entretenimiento']:
            for timer in modos.get(m, []):
                timer['modo'] = m  # Agregar el modo al timer para mostrarlo
                timers.append(timer)
        modo_actual = 'todos'

    # Ordenar los temporizadores por fecha (más reciente primero)
    if timers:
        timers = sorted(timers, key=lambda x: x.get('timestamp', datetime.min), reverse=True)

    return render(request, 'mis_timers.html', {
        'timers': timers,
        'escritorios': escritorios,
        'modo_actual': modo_actual,
        'message': request.session.pop('message', None)
    })

@session_required
def estadisticas(request):
    """
    Vista para mostrar estadísticas de uso de los escritorios
    """
    if request.session.get('tipo_usuario') != 'usuario':
        return redirect('dashboard')

    usuario = request.session.get('usuario')

    # Obtener parámetros de filtro
    escritorio_id = request.GET.get('escritorio', 'todos')
    modo = request.GET.get('modo', 'estudio')

    # Obtener escritorios asociados al usuario para el selector
    escritorios_cursor = escritorio_collection.find({
        "usuarios": usuario,
        "activo": True
    })

    escritorios = []
    for escritorio in escritorios_cursor:
        # Convertir _id a string
        escritorio['id'] = str(escritorio['_id'])
        escritorios.append(escritorio)

    # Obtener el usuario con sus datos de temporizador
    user = user_collection.find_one({"usuario": usuario})

    if not user:
        return redirect('login')

    # Obtener los datos del modo seleccionado
    modos = user.get('modos', {})
    datos_modo = modos.get(modo, [])

    # Filtrar por escritorio si es necesario
    if escritorio_id != 'todos':
        datos_modo = [dato for dato in datos_modo if dato.get('escritorio_id') == escritorio_id]

    # Calcular fechas para filtrar
    hoy = datetime.now()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    inicio_mes = datetime(hoy.year, hoy.month, 1)
    ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
    fin_mes = datetime(hoy.year, hoy.month, ultimo_dia)

    # Preparar datos para estadísticas
    datos_semana = []
    datos_mes = []

    # Formato para comparar fechas: "YYYY-MM-DD"
    for dato in datos_modo:
        fecha_str = dato.get('fecha_str', '')
        segundos = dato.get('seconds', 0)

        # Asegurar que segundos sea un número
        try:
            segundos = int(segundos)
        except (TypeError, ValueError):
            segundos = 0

        horas = segundos / 3600  # Convertir segundos a horas

        # Intentar diferentes formatos de fecha
        fecha = None
        try:
            # Primero intentar con el formato completo
            if fecha_str and ' ' in fecha_str:
                fecha_parte = fecha_str.split(' ')[0]
                fecha = datetime.strptime(fecha_parte, '%Y-%m-%d')
            else:
                continue
        except (ValueError, TypeError, AttributeError):
            # Si falla, intentar extraer la fecha de otra manera
            try:
                if isinstance(dato.get('timestamp'), datetime):
                    fecha = dato.get('timestamp')
                else:
                    continue
            except:
                continue

        if not fecha:
            continue

        # Filtrar por semana actual
        if inicio_semana.date() <= fecha.date() <= fin_semana.date():
            datos_semana.append({
                'fecha': fecha,
                'dia_semana': fecha.weekday(),  # 0=Lunes, 6=Domingo
                'horas': horas
            })

        # Filtrar por mes actual
        if inicio_mes.date() <= fecha.date() <= fin_mes.date():
            datos_mes.append({
                'fecha': fecha,
                'dia_mes': fecha.day,
                'horas': horas
            })

    # Calcular estadísticas por día de la semana
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    estadisticas_semana = []

    # Crear estructura para todos los días, aún sin datos
    for i, dia in enumerate(dias_semana):
        # Sumar horas para este día de la semana
        horas_dia = sum(dato['horas'] for dato in datos_semana if dato['dia_semana'] == i)
        estadisticas_semana.append({
            'dia': dia,
            'horas': round(horas_dia, 2)
        })

    # Calcular total del mes
    total_horas_mes = sum(dato['horas'] for dato in datos_mes)
    total_horas_mes = round(total_horas_mes, 2)

    return render(request, 'estadisticas.html', {
        'usuario': usuario,
        'escritorios': escritorios,
        'escritorio_seleccionado': escritorio_id,
        'modo_seleccionado': modo,
        'estadisticas_semana': estadisticas_semana,
        'total_horas_mes': total_horas_mes,
        'mes_actual': hoy.strftime('%B %Y')
    })

    return render(request, 'estadisticas.html', {
        'usuario': usuario,
        'escritorios': escritorios,
        'escritorio_seleccionado': escritorio_id,
        'modo_seleccionado': modo,
        'estadisticas_semana': estadisticas_semana,
        'total_horas_mes': round(total_horas_mes, 2),
        'mes_actual': hoy.strftime('%B %Y')
    })