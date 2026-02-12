from django.shortcuts import render, redirect
from .forms import SurveyForm, QuestionForm
from .models_mongo import Survey, Question, Response, Answer
from .models import SurveyLink
from bson.objectid import ObjectId
from django.contrib import messages
import plotly.express as px
import pandas as pd
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotFound, Http404
from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit

@ratelimit(key="user_or_ip", rate="10/m", block=True)
def home(request):
    return render(request, 'home.html')

def custom_404(request, exception):
    return render(request, '404.html', status=404)


@login_required
@ratelimit(key="user", rate="10/m",method="POST", block=True)
def SurveyView(request):
    if request.method == 'POST':
        form = SurveyForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            survey = Survey(
                title=data['title'],
                description=data['description']
            )
            survey.save()
            # save survey in sql database with name and survey_id
            save_link, created = SurveyLink.objects.update_or_create(user=request.user, name=data['title'], survey_id=survey.id)
            if created:
                save_link.link = request.build_absolute_uri(f"/start-survey/{save_link.unique_id}")
                save_link.save()

            return redirect(Question_View, survey_id=survey.id)
    else:
        form = SurveyForm()
    return render(request, 'survey.html', {'form': form})


@login_required
@ratelimit(key="user", rate="3/m",method="POST", block=True)
def Question_View(request, survey_id):
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            question_list = []
            question_type = data['question_type']
            options = data['options']
            if question_type in ['single_choice', 'multiple_choice', 'int', 'float'] and options:
                options = options.split(',')
                for option in options:
                    question_list.append(option.strip())

            question = Question(
                survey=ObjectId(survey_id),
                text=data['text'],
                question_type=question_type,
                options=question_list
            )
            question.save()
            return redirect(Question_View, survey_id=survey_id)
  
    else:
        form = QuestionForm()
        # get_object_or_404(SurveyLink, user = request.user.id, survey_id=survey_id)
    return render(request, 'question.html', {'form': form, 'survey_id': survey_id,})



@login_required
@ratelimit(key="user", rate="10/m", block=True)
def ShowAllSurveys(request):
    surveys = SurveyLink.objects.filter(user=request.user.id)
    return render(request, 'show_all_surveys.html', {'surveys': surveys})

@login_required
@ratelimit(key="user", rate="10/m", block=True)
def ShowSurveyView(request, survey_id):
    surveys = SurveyLink.objects.filter(user = request.user)
    for survey in surveys:
        if str(survey_id) == str(survey.survey_id):
            survey = Survey.objects.get(id=survey_id)
            questions = Question.objects.filter(survey=survey_id)
            return render(request, 'show_survey.html', {'survey': survey, 'questions': questions, 'survey_id': survey_id})
        
    
    raise Http404("Page not found")
        
@login_required
@ratelimit(key="user", rate="10/m", block=True)
def DeleteSurvey(request, survey_id):
    try:
        # Delete answers and responses related to this survey
        responses = Response.objects.filter(survey=survey_id)
        for response in responses:
            Answer.objects.filter(response=response.id).delete()
        responses.delete()

        # Delete all questions of this survey
        Question.objects.filter(survey=survey_id).delete()

        # Delete the survey itself
        Survey.objects.filter(id=survey_id).delete()

        # Delete the SurveyLink (if it exists)
        SurveyLink.objects.filter(survey_id=survey_id).delete()

        messages.success(request, 'Survey deleted successfully.')

        return redirect(ShowAllSurveys)

    except Survey.DoesNotExist:
        messages.error(request, 'Survey not found.')
        return redirect(ShowAllSurveys)


@login_required
@ratelimit(key="user", rate="10/m", block=True)
def BuildDiagram(request, survey_id):
    graphs = []
    get_object_or_404(SurveyLink, user=request.user.id, survey_id=survey_id)
    total_surveys = Response.objects.filter(survey=survey_id).count()
    try:
        questions = Question.objects.filter(survey=survey_id)
        for question in questions:
            if question.question_type != 'text':
                answers = Answer.objects.filter(question=question.id)
                answer_values = [answer.answer_value for answer in answers]

                df = pd.DataFrame(answer_values, columns=["Answer"])
                count = df["Answer"].value_counts()
                lebels = count.index.tolist()
                values = count.values.tolist()

                fig = px.bar(x=lebels, y=values, title=question.text, text=values)
                fig.update_traces(
                marker_color='rgb(30,144,255)',
                marker_line_color='black',
                marker_line_width=1,
                width=0.5, 
                textposition='outside'
                )

                fig.update_layout(
                    height=400,
                    width=600,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    bargap=0.3,
                    bargroupgap=0.1,
                    margin=dict(l=50, r=50, t=80, b=50),
                    title={
                        'y':0.95,
                        'x':0.5,
                        'xanchor':'center',
                        'yanchor':'top'
                    }
                )

                graph = fig.to_html(full_html=False)
                graphs.append(graph)

        return render(request, 'graphs/build_diagram.html', {'graphs': graphs, 'total_surveys': total_surveys})

    except Exception as e:
        
        return render(request, 'graphs/build_diagram.html', {'graphs': [], 'total_surveys': total_surveys})