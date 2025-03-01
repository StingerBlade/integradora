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
        return JsonResponse({'error': 'Las contraseñas no coinciden'}, status=400)

    if user_collection.find_one({"usuario": usuario}):
        return redirect('register')

    hash_password = make_password(password)
    modos_iniciales = {
        'estudio': [],
        'entretenimiento': [],
    }

    user_collection.insert_one({
        "usuario": usuario,
        "contrasena": hash_password,
        "email": email,
        "modos": modos_iniciales
    })

    return redirect('login')

def login(request):
    return render(request, 'login.html')

# Login de usuarios
@require_http_methods(["POST"])
def mlogin(request):
    usuario = request.POST.get('username')  # En la BD es 'usuario'
    password = request.POST.get('password')

    # Buscar en ambas colecciones
    user = user_collection.find_one({"usuario": usuario})
    admin = admin_collection.find_one({"usuario": usuario})

    if user and admin:
        return JsonResponse({'error': 'Conflicto: El usuario existe en ambas colecciones'}, status=500)

    # Determinar si es usuario o admin
    if user and check_password(password, user['contrasena']):
        request.session['usuario'] = usuario
        request.session['email'] = user['email']
        request.session['tipo_usuario'] = 'usuario'  # Guardar el tipo en la sesión
    elif admin and check_password(password, admin['contrasena']):
        request.session['usuario'] = usuario
        request.session['email'] = admin['email']
        request.session['tipo_usuario'] = 'admin'  # Guardar el tipo en la sesión
    else:
        return redirect('login')  # Si la autenticación falla, volver al login

    request.session.modified = True  # Asegurar que se guarde la sesión correctamente
    print(f'Sesión establecida para {usuario} como {request.session["tipo_usuario"]}')

    return redirect('dashboard')

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
        return redirect('login')  # Si no existe en ninguna colección, redirigir al login

    # Determinar el tipo de usuario basado en la colección en la que se encontró
    if user: #si el usuario vienen como none pues aqui no entra xd
        tipo_usuario = 'usuario'
        email = user.get('email', 'No disponible')
    else:
        tipo_usuario = 'admin'
        email = admin.get('email', 'No disponible')

    usuarios = []
    if tipo_usuario == 'admin':
        usuarios = list(user_collection.find({}, {"_id": 0, "usuario": 1, "email": 1, "modos": 1}))

    return render(request, 'dashboard.html', {
        'usuario': usuario,
        'email': email,
        'tipo_usuario': tipo_usuario,# Pasamos el tipo de usuario al template
        'usuarios': usuarios
    })


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
