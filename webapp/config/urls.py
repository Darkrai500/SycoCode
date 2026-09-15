from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path
from annotations import views

urlpatterns = [
    path("login/", views.sign_in, name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password/", views.password, name="password"),
    path("", views.home, name="home"),
    path("guide/", views.guide, name="guide"),
    path("evaluate/<str:group_id>/", views.evaluate, name="evaluate"),
    path("save/<str:unit_id>/", views.save, name="save"),
    path("control/", views.control, name="control"),
    path("control/case/<str:group_id>/", views.inspect_case, name="inspect_case"),
    path("control/assign/", views.assign, name="assign"),
    path("control/export/<str:kind>/", views.export, name="export"),
    path("admin/login/", views.sign_in),
    path("admin/", admin.site.urls),
]
