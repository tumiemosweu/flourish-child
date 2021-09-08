from django.apps import apps as django_apps
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist
from django.urls.base import reverse
from django.urls.exceptions import NoReverseMatch
from django_revision.modeladmin_mixin import ModelAdminRevisionMixin
from edc_base.sites.admin import ModelAdminSiteMixin
from edc_fieldsets import FieldsetsModelAdminMixin
from edc_metadata import NextFormGetter
from edc_model_admin import (
    ModelAdminNextUrlRedirectMixin, ModelAdminFormInstructionsMixin,
    ModelAdminFormAutoNumberMixin, ModelAdminAuditFieldsMixin,
    ModelAdminReadOnlyMixin, ModelAdminInstitutionMixin,
    FormAsJSONModelAdminMixin, ModelAdminRedirectOnDeleteMixin)
from simple_history.admin import SimpleHistoryAdmin

from edc_visit_tracking.modeladmin_mixins import (
    CrfModelAdminMixin as VisitTrackingCrfModelAdminMixin)

from .exportaction_mixin import ExportActionMixin


class ModelAdminMixin(ModelAdminNextUrlRedirectMixin,
                      ModelAdminFormInstructionsMixin,
                      ModelAdminFormAutoNumberMixin, ModelAdminRevisionMixin,
                      ModelAdminAuditFieldsMixin, ModelAdminReadOnlyMixin,
                      ModelAdminInstitutionMixin,
                      ModelAdminRedirectOnDeleteMixin,
                      ModelAdminSiteMixin,
                      ExportActionMixin):

    list_per_page = 10
    date_hierarchy = 'modified'
    empty_value_display = '-'
    next_form_getter_cls = NextFormGetter


class ChildCrfModelAdminMixin(
        VisitTrackingCrfModelAdminMixin, ModelAdminMixin,
        FieldsetsModelAdminMixin, FormAsJSONModelAdminMixin,
        SimpleHistoryAdmin, admin.ModelAdmin):

    show_save_next = True
    show_cancel = True
    appointment_model = 'flourish_child.appointment'

    post_url_on_delete_name = settings.DASHBOARD_URL_NAMES.get(
        'child_dashboard_url')

    def post_url_on_delete_kwargs(self, request, obj):
        return dict(
            subject_identifier=obj.child_visit.subject_identifier,
            appointment=str(obj.child_visit.appointment.id))

    def view_on_site(self, obj):
        dashboard_url_name = settings.DASHBOARD_URL_NAMES.get(
            'child_dashboard_url')
        try:
            url = reverse(
                dashboard_url_name, kwargs=dict(
                    subject_identifier=obj.child_visit.subject_identifier,
                    appointment=str(obj.child_visit.appointment.id)))
        except NoReverseMatch:
            url = super().view_on_site(obj)
        return url

    def get_appointment(self, request):
        """Returns the appointment instance for this request or None.
        """
        appointment_model_cls = django_apps.get_model(self.appointment_model)
        return appointment_model_cls.objects.get(
            pk=request.GET.get('appointment'))
        return None

    def get_previous_instance(self, request, instance=None, **kwargs):
        """Returns a model instance that is the first occurrence of a previous
        instance relative to this object's appointment.
        """
        obj = None
        appointment = instance or self.get_instance(request)
        while appointment:
            options = {
                '{}__appointment'.format(self.model.visit_model_attr()):
                appointment.previous_by_timepoint}
            try:
                obj = self.model.objects.get(**options)
            except ObjectDoesNotExist:
                pass
            else:
                break
            appointment = self.get_previous_appointment(request)
        return obj

    def get_instance(self, request):
        try:
            appointment = self.get_appointment(request)
        except ObjectDoesNotExist:
            return None
        else:
            return appointment

    def get_key(self, request, obj=None):
        schedule_name = None
        if self.get_previous_instance(request):
            try:
                model_obj = self.get_instance(request)
            except ObjectDoesNotExist:
                schedule_name = None
            else:
                schedule_name = model_obj.schedule_name
        return schedule_name
