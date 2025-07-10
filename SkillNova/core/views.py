from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from weasyprint import HTML
from .models import Training, Project, Assignment, Enrollment, ProjectCompletion
from .forms import AssignmentForm,ProjectCompletionForm

def index(request):
    return render(request, 'core/index.html')

def training_list(request):
    trainings = Training.objects.all()
    category = request.GET.get('category')
    tag = request.GET.get('tag')
    if category:
        trainings = trainings.filter(category=category)
    if tag:
        trainings = trainings.filter(tags__contains=tag)
    return render(request, 'core/training_list.html', {'trainings': trainings})

def training_detail(request, pk):
    training = get_object_or_404(Training, pk=pk)
    enrollment = None
    if request.user.is_authenticated:
        enrollment = Enrollment.objects.filter(user=request.user, training=training).first()
    return render(request, 'core/training_detail.html', {'training': training, 'enrollment': enrollment})

@login_required
def training_projects(request, pk):
    training = get_object_or_404(Training, pk=pk)
    enrollment = Enrollment.objects.filter(user=request.user, training=training).first()
    if not enrollment or (training.is_paid and not enrollment.is_paid):
        return redirect('training_detail', pk=pk)
    projects = training.projects.all().order_by('order')
    return render(request, 'core/training_projects.html', {'training': training, 'projects': projects})

@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    enrollment = Enrollment.objects.filter(user=request.user, training=project.training).first()
    if not enrollment or (project.training.is_paid and not enrollment.is_paid):
        return redirect('training_detail', pk=project.training.id)
    return render(request, 'core/project_detail.html', {'project': project})

@login_required
def project_instructions(request, pk):
    project = get_object_or_404(Project, pk=pk)
    enrollment = Enrollment.objects.filter(user=request.user, training=project.training).first()
    if not enrollment or (project.training.is_paid and not enrollment.is_paid):
        return redirect('training_detail', pk=project.training.id)
    return render(request, 'core/project_instructions.html', {'project': project})

@login_required
def project_assignments(request, pk):
    project = get_object_or_404(Project, pk=pk)
    enrollment = Enrollment.objects.filter(user=request.user, training=project.training).first()
    
    if not enrollment or (project.training.is_paid and not enrollment.is_paid):
        return redirect('training_detail', pk=project.training.id)

    assignments = list(project.assignments.all())  # ensure it's a list so it's iterable multiple times

    if request.method == 'POST':
        form = AssignmentForm(request.POST, assignments=assignments)
        if form.is_valid():
            correct_count = 0
            for assignment in assignments:
                answer = form.cleaned_data.get(f'answer_{assignment.id}')
                if answer == assignment.correct:
                    correct_count += 1
            total = len(assignments)
            if correct_count >= total * 0.8:  # 80% threshold
                ProjectCompletion.objects.get_or_create(enrollment=enrollment, project=project)
            # Update training progress
            completed_projects = ProjectCompletion.objects.filter(enrollment=enrollment).count()
            total_projects = project.training.projects.count()
            enrollment.progress = int((completed_projects / total_projects) * 100)
            enrollment.save()
            return render(request, 'core/assignment_result.html', {
                'correct_count': correct_count,
                'total': total,
                'progress': enrollment.progress
            })
    else:
        form = AssignmentForm(assignments=assignments)

    return render(request, 'core/project_assignments.html', {
        'project': project,
        'form': form,
        'assignments': assignments
    })

@login_required
def enroll(request):
    if request.method == 'POST':
        training_id = request.POST.get('training_id')
        training = get_object_or_404(Training, pk=training_id)
        # Directly enroll the user regardless of whether training is paid or free.
        enrollment, created = Enrollment.objects.get_or_create(user=request.user, training=training)
        enrollment.is_paid = True  # Mark as paid for direct enrollment.
        enrollment.save()
        return redirect('training_detail', pk=training_id)
    return redirect('training_list')

@login_required
def create_order(request):
    if request.method == 'POST':
        training_id = request.POST.get('training_id')
        training = get_object_or_404(Training, pk=training_id)
        # Directly mark the enrollment as paid (simulate direct enrollment)
        enrollment, _ = Enrollment.objects.get_or_create(user=request.user, training=training)
        enrollment.is_paid = True
        enrollment.save()
        return redirect('training_detail', pk=training_id)
    return redirect('training_list')

@login_required
def dashboard(request):
    enrollments = Enrollment.objects.filter(user=request.user).select_related('training')
    dashboard_data = []

    for enrollment in enrollments:
        training = enrollment.training
        projects = training.projects.all().order_by('order')

        project_cards = []
        for project in projects:
            completion = ProjectCompletion.objects.filter(enrollment=enrollment, project=project).first()
            completed = bool(completion and (completion.github_link or completion.linkedin_link))
            project_cards.append({
                'id': project.id,  # Add this line
                'title': project.title,
                'completed': completed,
                'github': completion.github_link if completion else None,
                'linkedin': completion.linkedin_link if completion else None
            })

        print(enrollment.progress)
        dashboard_data.append({
            'training': training,
            'progress': enrollment.progress,
            'projects': project_cards
        })

    return render(request, 'core/dashboard.html', {'dashboard_data': dashboard_data})

@login_required
def submit_project_links(request, pk):
    project = get_object_or_404(Project, pk=pk)
    enrollment = get_object_or_404(Enrollment, user=request.user, training=project.training)

    completion, created = ProjectCompletion.objects.get_or_create(enrollment=enrollment, project=project)

    if request.method == 'POST':
        form = ProjectCompletionForm(request.POST, instance=completion)
        if form.is_valid():
            form.save()
            # update progress
            completed_projects = ProjectCompletion.objects.filter(enrollment=enrollment).count()
            total_projects = project.training.projects.count()
            enrollment.progress = int((completed_projects / total_projects) * 100)
            enrollment.save()
            return redirect('dashboard')
    else:
        form = ProjectCompletionForm(instance=completion)

    return render(request, 'core/submit_project_links.html', {'form': form, 'project': project})

@login_required
def generate_certificate(request, training_id):
    training = get_object_or_404(Training, pk=training_id)
    enrollment = Enrollment.objects.filter(user=request.user, training=training).first()
    if not enrollment or enrollment.progress < 100:
        return HttpResponse("You have not completed the training yet.", status=403)
    html_string = f"""
    <html>
    <head><title>Certificate</title></head>
    <body style="text-align: center; font-family: Arial;">
    <h1>Certificate of Completion</h1>
    <p>This is to certify that <strong>{request.user.username}</strong> has successfully completed the training "<strong>{training.title}</strong>".</p>
    </body>
    </html>
    """
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="certificate_{training.id}.pdf"'
    return response
