from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from .models import user_collection, admin_collection
from django.contrib.auth.hashers import make_password, check_password
from functools import wraps
from django.views.decorators.csrf import csrf_exempt
import json

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
        "activo": True  # Campo nuevo que indica si el usuario está activo
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
        if not user.get('activo', True):  # Si no existe el campo, asumir que está activo
            return render(request, 'login.html', {'error': 'Esta cuenta ha sido desactivada. Contacte al administrador.'})

        request.session['usuario'] = usuario
        request.session['email'] = user['email']
        request.session['tipo_usuario'] = 'usuario'

        # Redirigir a los usuarios normales al dashboard de usuario
        return redirect('user_dashboard')

    elif admin and check_password(password, admin['contrasena']):
        # No verificamos 'activo' para administradores
        request.session['usuario'] = usuario
        request.session['email'] = admin['email']
        request.session['tipo_usuario'] = 'admin'

        # Redirigir a los administradores al dashboard de admin
        return redirect('dashboard')
    else:
        return render(request, 'login.html', {'error': 'Usuario o contraseña incorrectos'})

# Dashboard con sesión requerida
@session_required
def dashboard(request):
    usuario = request.session.get('usuario', 'Invitado')

    # Buscar en ambas colecciones
    user = user_collection.find_one({"usuario": usuario})
    admin = admin_collection.find_one({"usuario": usuario})
    tipo_usuario = request.session.get('tipo_usuario', 'usuario')

    if user and admin:
        return JsonResponse({'error': 'Conflicto: El usuario existe en ambas colecciones'}, status=500)

    if not user and not admin:
        return redirect('login')

    # Determinar el tipo de usuario basado en la colección en la que se encontró
    if user:
        tipo_usuario = 'usuario'
        email = user.get('email', 'No disponible')
    else:
        tipo_usuario = 'admin'
        email = admin.get('email', 'No disponible')

    usuarios = []
    if tipo_usuario == 'admin':
        # Incluir el campo activo en la consulta
        usuarios = list(user_collection.find({}, {"_id": 0, "usuario": 1, "email": 1, "modos": 1, "activo": 1}))

    # Mostrar mensaje de éxito si existe
    message = request.session.pop('message', None)

    return render(request, 'dashboard.html', {
        'usuario': usuario,
        'email': email,
        'tipo_usuario': tipo_usuario,
        'usuarios': usuarios,
        'message': message
    })

# Nueva función para editar usuarios sin JS
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

# Agregar una función para el cierre de sesión
def logout(request):
    if 'usuario' in request.session:
        del request.session['usuario']
    if 'email' in request.session:
        del request.session['email']
    if 'tipo_usuario' in request.session:
        del request.session['tipo_usuario']

    return redirect('index')

# Mantenemos la función original update_user por compatibilidad
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

            # Verificar si el nuevo nombre de usuario ya existe (si está cambiando)
            if old_usuario != usuario and user_collection.find_one({"usuario": usuario}):
                return JsonResponse({'error': 'El nombre de usuario ya está en uso'}, status=400)

            # Actualizar solo usuario y email, conservando los modos existentes
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
                # Si no se modificó ningún documento pero se encontró el usuario
                # puede ser que los datos sean los mismos
                return JsonResponse({'message': 'No se realizaron cambios'})

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Formato JSON inválido'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Método no permitido'}, status=405)


@session_required
def user_dashboard(request):
    if request.session.get('tipo_usuario') != 'usuario':
        return redirect('dashboard')  # Redirige a administradores al dashboard de admin

    usuario = request.session.get('usuario', 'Invitado')
    email = request.session.get('email', 'No disponible')

    return render(request, 'user_dashboard.html', {
        'usuario': usuario,
        'email': email
    })

