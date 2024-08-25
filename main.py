from datetime import datetime, timedelta, timezone
from fastapi import Depends, FastAPI, Request, HTTPException, status, Body
from middlewares.error_handler import ErrorHandler
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import paho.mqtt.client as mqtt
from typing import Annotated
from models import User   # Importa la clase User desde models.py
from config.mqtt import broker_config, topic_temperatura, topic_presion, topic_salida_esp32
from config.db_config import save_to_influxdb, dataDB_24_hs
from security.jwt_auth import create_access_token, authenticate_user, get_current_user, get_current_active_user
from security.jwt_auth import ACCESS_TOKEN_EXPIRE_MINUTES, super_users_db, Token, oauth2_scheme

app = FastAPI()
app.title = "Microservivio 1 Backend Avanzado - Recibe datos MQTT y almacena en InfluxDB."
app.version = "0.0.1"

app.add_middleware(ErrorHandler)
templates = Jinja2Templates(directory="templates")
# Datos para la plantilla HTML
data = {"temperatura": 0.0, "presion": 0.0}

# Función para cuando se recibe un mensaje por MQTT.
def on_message(client, userdata, message):
    topic = message.topic
    payload = message.payload.decode("utf-8")
    print(f"Mensaje recibido en el tema {topic}: {payload}")    
    global data
    if topic == topic_temperatura:
        data["temperatura"] = float(payload)
        save_to_influxdb("temperatura", float(payload))             # Almacena la temperatura en InfluxDB (Point)
    elif topic == topic_presion:
        data["presion"] = float(payload)
        save_to_influxdb("presion", float(payload))                 # Almacena la presión en InfluxDB (Point)

# Crear el cliente MQTT
client = mqtt.Client()
client.username_pw_set(broker_config["mqtt_username"], broker_config["mqtt_password"])
client.tls_set()                                        # Habilitar TLS para HiveMQ Cloud
client.on_message = on_message

# Conectar al broker MQTT
client.connect(broker_config["mqtt_broker"], broker_config["mqtt_port"], 60)
client.subscribe(topic_temperatura)
client.subscribe(topic_presion)
client.loop_start()

@app.post("/v1/token")     # Comprueba usuario y contraseña, si es correcto devuelve el token JWT.
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    user = authenticate_user(super_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    return Token(access_token=access_token, token_type="bearer")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "data": data})

@app.get("/v1/temperatura")
async def get_temperatura(current_user: Annotated[User, Depends(get_current_active_user)]):
    return JSONResponse({"temperatura": data["temperatura"]})

# Endpoint para obtener la presión
@app.get("/v1/presion")
async def get_presion(current_user: Annotated[User, Depends(get_current_active_user)]):
    return JSONResponse({"presion": data["presion"]})

@app.get("/v1/temperatura-24-hs")
async def get_presion(current_user: Annotated[User, Depends(get_current_active_user)]):
    return JSONResponse(dataDB_24_hs("temperatura"))

@app.get("/v1/presion-24-hs")
async def get_presion(current_user: Annotated[User, Depends(get_current_active_user)]):
    return JSONResponse(dataDB_24_hs("presion"))

# Endpoint para controlar la salida del ESP32
@app.post("/v1/salida_esp32/{estado}")
async def set_salida_esp32(estado: str, current_user: Annotated[User, Depends(get_current_active_user)]):
    if estado.lower() not in ["on", "off"]:
        raise HTTPException(status_code=400, detail="El estado debe ser 'on' o 'off'")
    client.publish(topic_salida_esp32, estado)
    return JSONResponse({"message": f"Salida del ESP32 establecida en {estado}"})