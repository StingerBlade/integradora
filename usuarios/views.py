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
        "activo": True  # Campo para soft delete
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

# Dashboard con sesión requerida
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

    # Mostrar mensaje de éxito si existe
    message = request.session.pop('message', None)

    return render(request, 'dashboard.html', {
        'usuario': usuario,
        'email': email,
        'tipo_usuario': tipo_usuario,
        'usuarios': usuarios,
        'escritorios': escritorios,
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

    nombre = request.POST.get('nombre')
    descripcion = request.POST.get('descripcion')

    if not nombre:
        request.session['message'] = {'type': 'error', 'text': 'El nombre del escritorio es obligatorio'}
        return redirect('admin_escritorios')

    # Generar un número de serie único de 6 dígitos
    numero_serie = ''.join(random.choices('0123456789', k=6))

    # Verificar que el número de serie no exista ya
    while escritorio_collection.find_one({"numero_serie": numero_serie}):
        numero_serie = ''.join(random.choices('0123456789', k=6))

    # Crear el escritorio
    nuevo_escritorio = {
        "nombre": nombre,
        "descripcion": descripcion,
        "usuarios": [],
        "activo": True,
        "numero_serie": numero_serie
    }

    escritorio_collection.insert_one(nuevo_escritorio)

    request.session['message'] = {'type': 'success', 'text': f'Escritorio "{nombre}" creado correctamente con número de serie: {numero_serie}'}
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
        request.session['message'] = {'type': 'error', 'text': 'Debe ingresar un número de serie'}
        return redirect('vincular_escritorio')

    # Buscar el escritorio por número de serie
    escritorio = escritorio_collection.find_one({
        "numero_serie": numero_serie,
        "activo": True
    })

    if not escritorio:
        request.session['message'] = {'type': 'error', 'text': 'Número de serie inválido o escritorio inactivo'}
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