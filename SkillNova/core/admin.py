# Register your models here.
from django.contrib import admin
from .models import Training, Project, Assignment, Enrollment, ProjectCompletion

class ProjectInline(admin.TabularInline):
    model = Project
    extra = 4
    max_num = 4  # Enforce exactly 4 projects

class TrainingAdmin(admin.ModelAdmin):
    inlines = [ProjectInline]

class ProjectAdmin(admin.ModelAdmin):
    list_filter = ('is_approved',)
    actions = ['approve_projects']

    def approve_projects(self, request, queryset):
        queryset.update(is_approved=True)
    approve_projects.short_description = "Approve selected projects"

admin.site.register(Training, TrainingAdmin)
admin.site.register(Project, ProjectAdmin)
admin.site.register(Assignment)
admin.site.register(Enrollment)
admin.site.register(ProjectCompletion)