import uvicorn
from http import server
from fastapi import FastAPI, Request, APIRouter, responses
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from core.config import settings
# from beanie import init_beanie
# from motor.motor_asyncio import AsyncIOMotorClient
from models.models_mongo import *
from api.api_v1.router import router
from schemas.note_schema import NoteAuth
from schemas.record_schema import RecordAuth
from services.record_service import RecordService
from services.user_service import UserService
from services.note_service import NoteService
from api.auth.forms import *
from api.auth.jwt import login, refresh_token
from api.deps.user_deps import get_current_user
from api.api_v1.hendlers.user import create_user
import time
from threading import Thread
from scrap.scrap import scraping
from api.api_v1.hendlers.record import *
from api.api_v1.hendlers import note
from services.dbox import *
from utils.e_mail import send_email
from utils.pass_gen import password_generator



app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)
api_router = APIRouter()


app.mount("/static", StaticFiles(directory="static"), name="static")



valute = {}
news = {}
sport = {}
weather = {}
reload_time = 0


def main_scrap():
    global valute, news, sport, weather, reload_time
    if reload_time + 900 < int(time.time()):
        valute, news, sport, weather = scraping()
        print('scrap new info')
        reload_time = time.time()
    # while True:
    #     global valute, news, sport, weather
    #     valute, news, sport, weather = scraping()
    #     time.sleep(900)  # перезапуск каждые 15 минут


# Thread(target=main_scrap, args=()).start()


recordService = RecordService()
userService = UserService()
noteService = NoteService()
templates = Jinja2Templates(directory="templates")


# @api_router.post('/dashboard', response_class=HTMLResponse)
# async def dashboard(request: Request):
#     token = request._cookies.get("access_token").split(" ")[1]
#     user = await get_current_user(token)
#     x = await list(user)
#     print(x)
#     return templates.TemplateResponse("dashboard/dashboard.html",
#                                       context={"request": request})


async def get_user(request):
    token = request._cookies.get("access_token").split(" ")[1]
    try:
        user = await get_current_user(token)
        return user
    except:
        new_token = await refresh_token(refresh_token=request._cookies.get("refresh_token"))
        user = await get_current_user(new_token.get('access_token'))
        return user


@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    main_scrap()

    if (request._cookies.get("access_token")):
        user = await get_user(request)
        return templates.TemplateResponse("index.html", 
                                         {"request": request,
                                          "valute": valute,
                                          "news": news,
                                          "sport": sport,
                                          "weather": weather,
                                          "user": user.__dict__})
    return templates.TemplateResponse("index.html",
                                     {"request": request,
                                      "valute": valute,
                                      "news": news,
                                      "sport": sport,
                                      "weather": weather,})


@app.post('/', response_class=HTMLResponse)
async def home(request: Request):
    main_scrap()
    user = await get_user(request)
    # x = await list(user)
    return templates.TemplateResponse("index.html",
                                     {"request": request,
                                      "valute": valute,
                                      "news": news,
                                      "sport": sport,
                                      "weather": weather,
                                      "user": user.__dict__})


@app.get('/signup', response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get('/contacts', response_class=HTMLResponse)
async def contacts(request: Request):
    user = await get_user(request)
    if not user:
        return responses.RedirectResponse('/signup')
    list_records = await list(user)
    return templates.TemplateResponse("contacts/contacts.html",
                                     {"request": request,
                                      "user": user.__dict__,
                                      "list":list_records,})



@app.post('/contacts', response_class=HTMLResponse)
async def contacts(request: Request):
    if (await request.form()).get("name"):
        form = ContactCreateForm(request)
    if (await request.form()).get("new_contact-id"):
        form = ContactUpdateForm(request)
    if (await request.form()).get("contact-id"):
        form = ContactDeleteForm(request)
    await form.load_data()
    user = await get_user(request)
    if not user:
        return responses.RedirectResponse('/signup')
    if type(form) == ContactCreateForm:
        if await form.is_valid():
            print(form.email)
            print(type(form.email))
            print(form.phones)
            print(type(form.phones))
            data = RecordAuth(name=form.name,
                              birth_date=form.birth_date,
                              address=form.address,
                              emails=[Emails(email=form.email)],
                              phones=[Phones(phone=form.phones)])
            new_contact = await create_record(data=data ,current_user=user)
        else:
            pass
    list_records = await list(user)
    if type(form) == ContactUpdateForm:
        print(form.email)
        print(type(form.email))
        print(form.phones)
        print(type(form.phones))
        data = RecordAuth(name=form.name, 
                          birth_date=form.birth_date,
                          address=form.address,
                          emails=[Emails(email=form.email)],
                          phones=[Phones(phone=form.phones)])
        await update(record_id=form.id, data=data, current_user=user)
    if type(form) == ContactDeleteForm:
        await delete(record_id=form.id, current_user=user)
    list_records = await list(user)
    return templates.TemplateResponse("contacts/contacts.html",
                                     {"request": request,
                                      "user": user.__dict__,
                                      "list":list_records})


@app.get('/notes', response_class=HTMLResponse)
async def notes(request: Request):
    user = await get_user(request)
    if not user:
        return responses.RedirectResponse('/signup')
    notes = await noteService.list_notes(user) 
    return templates.TemplateResponse("notes/notes_dashboard.html",
                                     {"request": request,
                                      "user": user.__dict__,
                                      "notes":notes})

@app.post('/notes', response_class=HTMLResponse)
async def notes(request: Request):
    x = await request.form()
    if (await request.form()).get("note-has-title"):
        form = NoteCreateForm(request)
    if (await request.form()).get("new_note-id"):
        form = NoteUpdateForm(request)
    if (await request.form()).get("note-id"):
        form = NoteDeleteForm(request)
    await form.load_data()
    user = await get_user(request)
    if not user:
        return responses.RedirectResponse('/signup')
    if type(form) == NoteCreateForm:
        data = NoteAuth(name=form.title,
                        records=[Record(description=form.description)],
                        tags=[Tag(name="")])
        new_note = await note.create_note(data=data, current_user=user)
    if type(form) == NoteUpdateForm:
        data = NoteAuth(name=form.title,
                        records=[Record(description=form.description)])
        new_note = await note.update(note_id=form.id,
                                     data=data,
                                     current_user=user)
    if type(form) == NoteDeleteForm:
        await note.delete(note_id=form.id, current_user=user)
    notes = await noteService.list_notes(user)
    return templates.TemplateResponse("notes/notes_dashboard.html",
                                     {"request": request,
                                      "user": user.__dict__,
                                      "notes":notes,
                                      })


@app.get('/files', response_class=HTMLResponse)
async def files(request: Request):
    user_links = ''
    user = await get_user(request)
    if not user:
        return responses.RedirectResponse('/signup')
    links = ""
    token = True
    user_token = True
    try:
        links = dropbox_get_link()
    except:
        print("no valid token for common files")
        token = False
    try:
        user_links = dropbox_get_link(dropbox_token=request._cookies.get("user_dropbox_access_token"))
    except:
        print("no valid token")
        user_token = False
    return templates.TemplateResponse("files/files.html",
                                     {"request": request,
                                      "user": user.__dict__,
                                      "links":links,
                                      "user_links":user_links,
                                      "token": token,
                                      "user_token": user_token
                                      })


@app.post('/files', response_class=HTMLResponse)
async def files(request: Request):
    user_links = ''
    user = await get_user(request)
    if not user:
        return responses.RedirectResponse('/signup')
    links = ""
    token = True
    user_token = True
    try:
        links = dropbox_get_link()
    except:
        print("no valid token for common files")
        token = False
    try:
        user_links = dropbox_get_link(dropbox_token=request._cookies.get("user_dropbox_access_token"))
    except:
        print("no valid token")
        user_token = False
    return templates.TemplateResponse("files/files.html",
                                     {"request": request,
                                      "user": user.__dict__,
                                      "links":links,
                                      "user_links":user_links,
                                      "token": token,
                                      "user_token": user_token})
 

@app.post('/uploadfiles', response_class=HTMLResponse)
async def files(request: Request):
    user = await get_user(request)
    if not user:
        return responses.RedirectResponse('/signup')
    if (await request.form()).get("file"):
        form = FileUploadForm(request)
        await form.load_data()
        dropbox_upload_binary_file(binary_file=form.file.file._file,
                                   dropbox_file_path=form.file.filename)
    if (await request.form()).get("user_file"):
        form = FileUserUploadForm(request)
        await form.load_data()
        dropbox_upload_binary_file(binary_file=form.file.file._file,
                                   dropbox_file_path=form.file.filename,
                                   dropbox_token=request._cookies.get("user_dropbox_access_token"))
    if (await request.form()).get("token"):
        form = FileAccessTokenForm(request)
        await form.load_data()
        user_dropbox_access_token = form.token
        redirectresponse = responses.RedirectResponse('/files')
        redirectresponse.set_cookie(key="user_dropbox_access_token", value=user_dropbox_access_token) 
        try:
            user_links = dropbox_get_link(user_dropbox_access_token)
            return redirectresponse
        except:
            error_massege = 'Enter your access token in form'
    links = ""
    token = True
    user_token = True
    user_links = ''
    try:
        links = dropbox_get_link()
    except:
        print("no valid token for common files")
        token = False
    try:
        user_links = dropbox_get_link(dropbox_token=request._cookies.get("user_dropbox_access_token"))
    except:
        print("no valid token")
        user_token = False
    return templates.TemplateResponse("files/files.html",
                                     {"request": request,
                                      "user": user.__dict__,
                                      "links":links,
                                      "user_links":user_links,
                                      "token": token,
                                      "user_token": user_token})


# @app.get('/signup')
@app.post('/signup')
async def signup(request: Request):
    if (await request.form()).get("registerName"):
        form = UserCreateForm(request)
    if (await request.form()).get("loginEmail"):
        form = LoginForm(request)
    await form.load_data()
    if await form.is_valid():
        if type(form) == LoginForm:
            form.__dict__.update(msg="Login Successful :)")
            response = templates.TemplateResponse("dashboard/dashboard.html",
                                                form.__dict__)
            token = await login(response=response, form_data=form)
            redirectresponse = responses.RedirectResponse('/')
            redirectresponse.set_cookie(key="access_token",
                                value=f'Bearer {token.get("access_token")}')
            redirectresponse.set_cookie(key="refresh_token",
                                value=f'{token.get("refresh_token")}')
            return redirectresponse
        elif type(form) == UserCreateForm:
            form.__dict__.update(msg="Login Successful :)")
            response = templates.TemplateResponse("dashboard/dashboard.html",
                                                form.__dict__)
            await create_user(data=form)
            form.username = form.email
            token = await login(response=response, form_data=form)
            redirectresponse = responses.RedirectResponse('/')
            redirectresponse.set_cookie(key="access_token",
                                value=f'Bearer {token.get("access_token")}')
            redirectresponse.set_cookie(key="refresh_token",
                                value=f'{token.get("refresh_token")}')
            return redirectresponse
    return templates.TemplateResponse("/login.html", context={"request": request})


@app.get('/presentation', response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("presentation.html",
                                      {"request": request})


@app.get("/logout")
async def logout(request: Request):
    user = await get_user(request)
    redirectresponse = responses.RedirectResponse('/signup')
    redirectresponse.delete_cookie(key ='access_token')
    redirectresponse.delete_cookie(key ='refresh_token')
    redirectresponse.delete_cookie(key ='user_dropbox_access_token')
    return redirectresponse


@app.post('/send_email')
async def send_email_route(request: Request):
    print('start send_email route')
    # redirectresponse = responses.RedirectResponse('/signup')
    email = (await request.form()).get("email")
    await send_email(to_email=email, subject='Your new password for Pocket Memory', body=password_generator())
    return templates.TemplateResponse("/login.html", context={"request": request})


@app.on_event("startup")
async def start_db():
    await init_db()
# async def init_db():
#     """
#         initialize crucial application services
#     """
#     db_client = AsyncIOMotorClient(settings.MONGO_CONNECTION_STRING).MyHelperMongoDB
#     await init_beanie(
#         database=db_client,
#         document_models= [Note, Tag, Record, Emails, Phones, Records, User])


web_router = APIRouter()
web_router.include_router(router=api_router, prefix='', tags=["web-app"])
app.include_router(web_router, prefix=settings.API_V1_STR)
app.include_router(router, prefix=settings.API_V1_STR)



# uvicorn app:app --reload
if __name__ == "__main__":
    config = uvicorn.Config("app:app", 
                            port=8080, 
                            log_level="info", 
                            reload=True,
                            host="0.0.0.0",
                            forwarded_allow_ips='*')
    server = uvicorn.Server(config)
    server.run()
