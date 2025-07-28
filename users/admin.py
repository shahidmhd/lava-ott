from django.contrib import admin

from .models import User
from .models import Project
from .models import DeletedUser, CustomSession


admin.site.register(User)
admin.site.register(Project)
admin.site.register(DeletedUser)
admin.site.register(CustomSession)
