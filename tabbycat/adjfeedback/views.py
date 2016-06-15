from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.generic.base import TemplateView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import FormView

from actionlog.mixins import LogActionMixin
from actionlog.models import ActionLogEntry
from participants.models import Adjudicator, Team
from results.mixins import PublicSubmissionFieldsMixin, TabroomSubmissionFieldsMixin
from tournaments.mixins import PublicTournamentPageMixin, TournamentMixin

from utils.misc import reverse_tournament
from utils.mixins import CacheMixin, JsonDataResponseView, SingleObjectByRandomisedUrlMixin, SingleObjectFromTournamentMixin
from utils.mixins import HeadlessTemplateView, PostOnlyRedirectView, SuperuserOrTabroomAssistantTemplateResponseMixin, SuperuserRequiredMixin, VueTableMixin
from utils.urlkeys import populate_url_keys

from .models import AdjudicatorFeedback, AdjudicatorTestScoreHistory
from .forms import make_feedback_form_class
from .utils import get_feedback_overview, get_feedback_progress, progress_cells


class GetAdjScores(JsonDataResponseView, LoginRequiredMixin, TournamentMixin):

    def get_data(self):
        data = {}
        for adj in Adjudicator.objects.all().select_related('tournament', 'tournament__current_round'):
            data[adj.id] = adj.score
        return data


class FeedbackOverview(LoginRequiredMixin, TournamentMixin, VueTableMixin, HeadlessTemplateView):

    template_name = 'feedback_overview.html'
    page_title = 'Adjudicator Feedback Summary'
    page_emoji = '🙅'
    sort_key = 'Score'

    def get_adjudicators(self):
        t = self.get_tournament()
        if t.pref('share_adjs'):
            return Adjudicator.objects.filter(Q(tournament=t) | Q(tournament__isnull=True))
        else:
            return Adjudicator.objects.filter(tournament=t)

    def get_context_data(self, **kwargs):
        kwargs['breaking_count'] = self.get_adjudicators().count()
        return super().get_context_data(**kwargs)

    def get_table_data(self):
        t = self.get_tournament()
        adjudicators = get_feedback_overview(t, self.get_adjudicators())

        feedback_data = []
        for adj in adjudicators:
            ddict = []
            ddict.extend(self.adj_cells(adj, t, hide_institution=True))
            ddict[0]['cell']['text'] += "<br><em>%s</em>" % adj.institution.code

            if t.pref('show_unaccredited'):
                ddict.append({
                    'head': {'key': 'N', 'icon': 'glyphicon-leaf', 'tooltip': 'Novice Status'},
                    'cell': {'icon': 'glyphicon-ok' if adj.novice else ''}
                })

            checkbox = '<input type="checkbox" adj_id=%s' % adj.id
            checkbox += ' checked >' if adj.breaking else '>'
            ddict.append({
                'head': {'key': 'B', 'icon': 'glyphicon-star', 'tooltip': 'Whether the adj is marked as breaking (click to mark)'},
                'cell': {'text': checkbox, 'sort': adj.breaking, 'class': 'double-height toggle_breaking_status'}
            })

            current_score = str(self.format_cell_number(adj.feedback_score, dp=1)) if adj.feedback_score else 'N/A'
            ddict.append({
                'head': {'key': 'Score', 'icon': 'glyphicon-signal', 'tooltip': 'Current weighted score'},
                'cell': {'text': '<strong>%s</strong>' % current_score, 'tooltip': 'Current weighted average of all feedback', 'class': 'double-height'}
            })

            ddict.append({
                'head': {
                    'key': 'Test', 'icon': 'glyphicon-scale', 'tooltip': 'Test Score Result'
                },
                'cell': {
                    'text': self.format_cell_number(adj.score, dp=1),
                    'modal': adj.id,
                    'class': 'edit-test-score double-height',
                    'tooltip': 'Click to edit test score'
                }
            })

            ddict.append({
                'head': {
                    'key': 'Feedback',
                    'text': 'Feedback as <span class="position-display chair">&nbsp;Chair&nbsp;</span>' +
                    ' <span class="position-display panellist">&nbsp;Panellist&nbsp;</span>' +
                    ' <span class="position-display trainee">&nbsp;Trainee&nbsp;</span>'
                },
                'cell': {
                    'data': adj.feedback_data,
                    'component': 'feedback-trend',
                    'min-score': t.pref('adj_min_score'),
                    'max-score': t.pref('adj_max_score'),
                    'round-seq': t.current_round.seq,
                }
            })

            ddict.append({
                'head': {'key': 'VF', 'icon': 'glyphicon-question-sign'},
                'cell': {'text': 'View<br>Feedback',
                         'class': 'view-feedback',
                         'link': reverse_tournament('adjfeedback-view-on-adjudicator', t, kwargs={'pk': adj.pk})}
            })
            # TODO
            if t.pref('enable_adj_notes'):
                ddict.append({
                    'head': {'key': 'NO', 'icon': 'glyphicon-list-alt'},
                    'cell': {'text': 'Edit<br>Note', 'class': 'edit-note', 'modal': str(adj.id) + '===' + str(adj.notes)}
                })
            # TODO: adj checkbox
            ddict.append({
                'head': {'key': 'DD', 'icon': 'glyphicon-eye-open', 'tooltip': 'Debates adjudicated'},
                'cell': {'text': adj.debates, 'class': 'double-height'}
            })
            ddict.append({
                'head': {'key': 'DD', 'icon': 'glyphicon-resize-full', 'tooltip': 'Average Margin (top) and Average Score (bottom)'},
                'cell': {'text': "%s<br>%s" % (self.format_cell_number(adj.avg_margin, dp=1), self.format_cell_number(adj.avg_score, dp=1))}
            })

            feedback_data.append(ddict)

        return feedback_data


class FeedbackByTargetView(LoginRequiredMixin, TournamentMixin, VueTableMixin, HeadlessTemplateView):
    template_name = "feedback_base.html"
    page_title = 'Find Feedback on Adjudicator'
    page_emoji = '🔍'
    sort_key = 'Name'

    def get_table_data(self):
        t = self.get_tournament()

        on_adjs_data = []
        for adj in Adjudicator.objects.filter(tournament=t):
            ddict = self.adj_cells(adj, t)

            feedbacks = AdjudicatorFeedback.objects.filter(adjudicator=adj).count(),
            ddict.append({
                'head': {'key': 'Feedbacks'},
                'cell': {
                    'text': "%s Feedbacks" % feedbacks,
                    'link': reverse_tournament('adjfeedback-view-on-adjudicator', t, kwargs={'pk': adj.id})
                }
            })
            on_adjs_data.append(ddict)

        return on_adjs_data


class FeedbackBySourceView(LoginRequiredMixin, TournamentMixin, VueTableMixin, HeadlessTemplateView):

    template_name = "feedback_base.html"
    tables_titles = ['From Teams', 'From Adjudicators', 'On Adjudicators']
    page_title = 'Find Feedback'
    page_emoji = '🔍'
    sort_key = 'Feedbacks'

    def get_tables_data(self):
        t = self.get_tournament()

        teams_data = []
        for team in Team.objects.filter(tournament=t):
            ddict = self.team_cells(team, t)

            feedbacks = AdjudicatorFeedback.objects.filter(
                source_team__team=team).select_related(
                'source_team__team').count()
            ddict.append({
                'head': {'key': 'Feedbacks'},
                'cell': {
                    'text': "%s Feedbacks" % feedbacks,
                    'link': reverse_tournament('adjfeedback-view-from-team', t, kwargs={'pk': team.id})
                }
            })
            teams_data.append(ddict)

        from_adjs_data = []
        for adj in Adjudicator.objects.filter(tournament=t):
            ddict = self.adj_cells(adj, t)

            feedbacks = AdjudicatorFeedback.objects.filter(
                source_adjudicator__adjudicator=adj).select_related(
                'source_adjudicator__adjudicator').count(),
            ddict.append({
                'head': {'key': 'Feedbacks'},
                'cell': {
                    'text': "%s Feedbacks" % feedbacks,
                    'link': reverse_tournament('adjfeedback-view-from-adjudicator', t, kwargs={'pk': adj.id})
                }
            })
            from_adjs_data.append(ddict)

        return [teams_data, from_adjs_data]


class FeedbackCardsView(LoginRequiredMixin, TournamentMixin, TemplateView):
    """Base class for views displaying feedback as cards."""

    def get_score_thresholds(self):
        tournament = self.get_tournament()
        min_score = tournament.pref('adj_min_score')
        max_score = tournament.pref('adj_max_score')
        score_range = max_score - min_score
        return {
            'low_score'     : min_score + score_range / 10,
            'medium_score'  : min_score + score_range / 5,
            'high_score'    : max_score - score_range / 10,
        }

    def get_feedbacks(self):
        questions = self.get_tournament().adj_feedback_questions
        feedbacks = self.get_feedback_queryset()
        for feedback in feedbacks:
            feedback.items = []
            for question in questions:
                try:
                    answer = question.answer_set.get(feedback=feedback).answer
                except ObjectDoesNotExist:
                    continue
                feedback.items.append({'question': question, 'answer': answer})
        return feedbacks

    def get_feedback_queryset(self):
        raise NotImplementedError()

    def get_context_data(self, **kwargs):
        kwargs['feedbacks'] = self.get_feedbacks()
        kwargs['score_thresholds'] = self.get_score_thresholds()
        return super().get_context_data(**kwargs)


class LatestFeedbackView(FeedbackCardsView):
    """View displaying the latest feedback."""

    template_name = "feedback_latest.html"

    def get_feedback_queryset(self):
        return AdjudicatorFeedback.objects.order_by('-timestamp')[:50].select_related(
            'adjudicator', 'source_adjudicator__adjudicator', 'source_team__team')


class FeedbackFromSourceView(SingleObjectMixin, FeedbackCardsView):
    """Base class for views displaying feedback from a given team or adjudicator."""
    # SingleObjectFromTournamentMixin doesn't work great here, it induces an MRO
    # conflict between TournamentMixin and ContextMixin.

    template_name = "feedback_by_source.html"
    source_name_attr = None
    source_type = "from"
    adjfeedback_filter_field = None

    def get_context_data(self, **kwargs):
        kwargs['source_name'] = getattr(self.object, self.source_name_attr, '<ERROR>')
        kwargs['source_type'] = self.source_type
        return super().get_context_data(**kwargs)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        # from SingleObjectFromTournamentMixin
        return super().get_queryset().filter(tournament=self.get_tournament())

    def get_feedback_queryset(self):
        kwargs = {self.adjfeedback_filter_field: self.object}
        return AdjudicatorFeedback.objects.filter(**kwargs).order_by('-timestamp')


class FeedbackOnAdjudicatorView(FeedbackFromSourceView):
    """Base class for views displaying feedback from a given team or adjudicator."""
    # SingleObjectFromTournamentMixin doesn't work great here, it induces an MRO
    # conflict between TournamentMixin and ContextMixin.

    model = Adjudicator
    source_name_attr = 'name'
    source_type = "on"
    adjfeedback_filter_field = 'adjudicator'


class FeedbackFromTeamView(FeedbackFromSourceView):
    """View displaying feedback from a given source."""
    model = Team
    source_name_attr = 'short_name'
    adjfeedback_filter_field = 'source_team__team'


class FeedbackFromAdjudicatorView(FeedbackFromSourceView):
    """View displaying feedback from a given adjudicator."""
    model = Adjudicator
    source_name_attr = 'name'
    adjfeedback_filter_field = 'source_adjudicator__adjudicator'


class GetAdjFeedback(JsonDataResponseView, LoginRequiredMixin, TournamentMixin):

    def parse_feedback(self, f, questions):

        if f.source_team:
            source_annotation = " (" + f.source_team.result + ")"
        elif f.source_adjudicator:
            source_annotation = " (" + f.source_adjudicator.get_type_display() + ")"
        else:
            source_annotation = ""

        data = [
            str(f.round.abbreviation),
            str(str(f.version) + (f.confirmed and "*" or "")),
            f.debate.bracket,
            f.debate.matchup,
            str(str(f.source) + source_annotation),
            f.score,
        ]
        for question in questions:
            try:
                data.append(question.answer_set.get(feedback=f).answer)
            except ObjectDoesNotExist:
                data.append("-")
        data.append(f.confirmed)
        return data

    def get_data(self):
        t = self.get_tournament()
        adj = get_object_or_404(Adjudicator, pk=int(self.request.GET['id']))
        feedback = adj.get_feedback().filter(confirmed=True)
        questions = t.adj_feedback_questions

        data = [self.parse_feedback(f, questions) for f in feedback]
        return {'aaData': data}


class BaseAddFeedbackIndexView(TournamentMixin, TemplateView):

    def get_context_data(self, **kwargs):
        tournament = self.get_tournament()
        kwargs['adjudicators'] = tournament.adjudicator_set.all() if not tournament.pref('share_adjs') \
            else Adjudicator.objects.all()
        kwargs['teams'] = tournament.team_set.all()
        return super().get_context_data(**kwargs)


class TabroomAddFeedbackIndexView(SuperuserOrTabroomAssistantTemplateResponseMixin, BaseAddFeedbackIndexView):
    """View for the index page for tabroom officials to add feedback. The index
    page lists all possible sources; officials should then choose the author
    of the feedback."""

    superuser_template_name = 'add_feedback.html'
    assistant_template_name = 'assistant_add_feedback.html'


class PublicAddFeedbackIndexView(CacheMixin, PublicTournamentPageMixin, BaseAddFeedbackIndexView):
    """View for the index page for public users to add feedback. The index page
    lists all possible sources; public users should then choose themselves."""

    template_name = 'public_add_feedback.html'
    public_page_preference = 'public_feedback'


class BaseAddFeedbackView(LogActionMixin, SingleObjectFromTournamentMixin, FormView):
    """Base class for views that allow users to add feedback.
    Subclasses must also subclass SingleObjectMixin, directly or indirectly."""

    template_name = "enter_feedback.html"
    pk_url_kwarg = 'source_id'

    def get_form_class(self):
        return make_feedback_form_class(
            self.object, self.get_submitter_fields(), **self.feedback_form_class_kwargs)

    def get_action_log_fields(self, **kwargs):
        kwargs['adjudicator_feedback'] = self.adj_feedback
        return super().get_action_log_fields(**kwargs)

    def form_valid(self, form):
        self.adj_feedback = form.save()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        source = self.object
        if isinstance(source, Adjudicator):
            kwargs['source_type'] = "adj"
        elif isinstance(source, Team):
            kwargs['source_type'] = "team"
        kwargs['source_name'] = self.source_name
        return super().get_context_data(**kwargs)

    def _populate_source(self):
        self.object = self.get_object()  # For compatibility with SingleObjectMixin
        if isinstance(self.object, Adjudicator):
            self.source_name = self.object.name
        elif isinstance(self.object, Team):
            self.source_name = self.object.short_name
        else:
            self.source_name = "<ERROR>"

    def get(self, request, *args, **kwargs):
        self._populate_source()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self._populate_source()
        return super().post(request, *args, **kwargs)


class TabroomAddFeedbackView(TabroomSubmissionFieldsMixin, LoginRequiredMixin, BaseAddFeedbackView):
    """View for tabroom officials to add feedback."""

    action_log_type = ActionLogEntry.ACTION_TYPE_FEEDBACK_SAVE
    feedback_form_class_kwargs = {
        'confirm_on_submit': True,
        'enforce_required': False,
        'include_unreleased_draws': True,
    }

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, "Feedback from {} on {} added.".format(
            self.source_name, self.adj_feedback.adjudicator.name))
        return result

    def get_success_url(self):
        return reverse_tournament('adjfeedback-add-index', self.get_tournament())


class PublicAddFeedbackView(PublicSubmissionFieldsMixin, PublicTournamentPageMixin, BaseAddFeedbackView):
    """Base class for views for public users to add feedback."""

    action_log_type = ActionLogEntry.ACTION_TYPE_FEEDBACK_SUBMIT
    feedback_form_class_kwargs = {
        'confirm_on_submit': True,
        'enforce_required': True,
        'include_unreleased_draws': False,
    }

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, "Thanks, your feedback on has been recorded.")
        return result

    def get_success_url(self):
        return reverse_tournament('tournament-public-index', self.get_tournament())


class PublicAddFeedbackByRandomisedUrlView(SingleObjectByRandomisedUrlMixin, PublicAddFeedbackView):
    """View for public users to add feedback, where the URL is a randomised one."""
    public_page_preference = 'public_feedback_randomised'


class PublicAddFeedbackByIdUrlView(PublicAddFeedbackView):
    """View for public users to add feedback, where the URL is by object ID."""
    public_page_preference = 'public_feedback'


class AdjudicatorActionError(RuntimeError):
    pass


class BaseAdjudicatorActionView(LogActionMixin, SuperuserRequiredMixin, TournamentMixin, PostOnlyRedirectView):

    def get_action_log_fields(self, **kwargs):
        kwargs['adjudicator'] = self.adjudicator
        return super().get_action_log_fields(**kwargs)

    def get_redirect_url(self):
        return reverse_tournament('adjfeedback-overview', self.get_tournament())

    def get_adjudicator(self, request):
        try:
            adj_id = int(request.POST["adj_id"])
            adjudicator = Adjudicator.objects.get(id=adj_id)
        except (ValueError, Adjudicator.DoesNotExist, Adjudicator.MultipleObjectsReturned):
            raise AdjudicatorActionError("Whoops! I didn't recognise that adjudicator: {}".format(adj_id))
        return adjudicator

    def post(self, request, *args, **kwargs):
        try:
            self.adjudicator = self.get_adjudicator(request)
            self.modify_adjudicator(request, self.adjudicator)
            self.log_action()  # Need to call explicitly, since this isn't a form view
        except AdjudicatorActionError as e:
            messages.error(request, str(e))

        return super().post(request, *args, **kwargs)


class SetAdjudicatorTestScoreView(BaseAdjudicatorActionView):

    action_log_type = ActionLogEntry.ACTION_TYPE_TEST_SCORE_EDIT

    def get_action_log_fields(self, **kwargs):
        kwargs['adjudicator_test_score_history'] = self.atsh
        # Skip BaseAdjudicatorActionView
        return super(BaseAdjudicatorActionView, self).get_action_log_fields(**kwargs)

    def modify_adjudicator(self, request, adjudicator):
        try:
            score = float(request.POST["test_score"])
        except ValueError:
            raise AdjudicatorActionError("Whoops! The value isn't a valid test score.")

        adjudicator.test_score = score
        adjudicator.save()

        atsh = AdjudicatorTestScoreHistory(
            adjudicator=adjudicator, round=self.get_tournament().current_round,
            score=score)
        atsh.save()
        self.atsh = atsh


class SetAdjudicatorBreakingStatusView(BaseAdjudicatorActionView):

    action_log_type = ActionLogEntry.ACTION_TYPE_ADJUDICATOR_BREAK_SET

    def modify_adjudicator(self, request, adjudicator):
        adjudicator.breaking = (str(request.POST["adj_breaking_status"]) == "true")
        adjudicator.save()

    def post(self, request, *args, **kwargs):
        super().post(request, *args, **kwargs)  # Discard redirect
        return HttpResponse("ok")


class SetAdjudicatorNoteView(BaseAdjudicatorActionView):

    action_log_type = ActionLogEntry.ACTION_TYPE_ADJUDICATOR_NOTE_SET

    def modify_adjudicator(self, request, adjudicator):
        try:
            note = str(request.POST["note"])
        except ValueError as e:
            raise AdjudicatorActionError("Whoop! There was an error interpreting that string: " + str(e))

        adjudicator.notes = note
        adjudicator.save()


class BaseFeedbackProgress(TournamentMixin, SuperuserRequiredMixin, VueTableMixin, HeadlessTemplateView):

    page_title = "Missing Feedback Ballots"
    page_emoji = "🆘"
    sort_key = 'Coverage'
    tables_titles = ['Adjudicators', 'Speakers']

    def get_tables_data(self):
        t = self.get_tournament()
        team_progress, adj_progress = get_feedback_progress(t)

        teams_progress_data = []
        for team in team_progress:
            ddict = []
            ddict.extend(progress_cells(team))
            ddict.extend(self.team_cells(team, t))
            teams_progress_data.append(ddict)

        adjs_progress_data = []
        for adj in adj_progress:
            ddict = []
            ddict.extend(progress_cells(team))
            ddict.extend(self.adj_cells(adj, t))
            adjs_progress_data.append(ddict)

        return [teams_progress_data, adjs_progress_data]


class FeedbackProgress(BaseFeedbackProgress):
    template_name = 'feedback_base.html'


class PublicFeedbackProgress(BaseFeedbackProgress, PublicTournamentPageMixin, CacheMixin):
    public_page_preference = 'feedback_progress'


class RandomisedUrlsView(SuperuserRequiredMixin, TournamentMixin, TemplateView):

    template_name = 'randomised_urls.html'

    def get_context_data(self, **kwargs):
        tournament = self.get_tournament()
        kwargs['teams'] = tournament.team_set.all()
        if not tournament.pref('share_adjs'):
            kwargs['adjs'] = tournament.adjudicator_set.all()
        else:
            kwargs['adjs'] = Adjudicator.objects.all()
        kwargs['exists'] = tournament.adjudicator_set.filter(url_key__isnull=False).exists() or \
            tournament.team_set.filter(url_key__isnull=False).exists()
        kwargs['tournament_slug'] = tournament.slug
        return super().get_context_data(**kwargs)


class GenerateRandomisedUrlsView(SuperuserRequiredMixin, TournamentMixin, PostOnlyRedirectView):

    def get_redirect_url(self):
        return reverse_tournament('randomised-urls-view', self.get_tournament())

    def post(self, request, *args, **kwargs):
        tournament = self.get_tournament()

        # Only works if there are no randomised URLs now
        if tournament.adjudicator_set.filter(url_key__isnull=False).exists() or \
                tournament.team_set.filter(url_key__isnull=False).exists():
            messages.error(
                self.request, "There are already randomised URLs. " +
                "You must use the Django management commands to populate or " +
                "delete randomised URLs.")
        else:
            populate_url_keys(tournament.adjudicator_set.all())
            populate_url_keys(tournament.team_set.all())
            messages.success(self.request, "Randomised URLs were generated for all teams and adjudicators.")

        return super().post(request, *args, **kwargs)
