from django import forms
from edc_appointment.form_validators import AppointmentFormValidator
from edc_base.sites.forms import SiteModelFormMixin
from edc_form_validators import FormValidatorMixin
import pytz

from ..models import Appointment


class AppointmentForm(SiteModelFormMixin, FormValidatorMixin, AppointmentFormValidator,
                      forms.ModelForm):
    """Note, the appointment is only changed, never added,
    through this form.
    """

    appointment_model = 'flourish_child.appointment'

    def clean(self):
        super().clean()

        cleaned_data = self.cleaned_data

        if cleaned_data.get('appt_datetime'):

            visit_definition = self.instance.visits.get(self.instance.visit_code)

            earlist_appt_date = (self.instance.timepoint_datetime -
                                 visit_definition.rlower).astimezone(
                pytz.timezone('Africa/Gaborone'))
            latest_appt_date = (self.instance.timepoint_datetime +
                                visit_definition.rupper).astimezone(
                pytz.timezone('Africa/Gaborone'))

            if self.instance.visit_code_sequence == 0:
                if (cleaned_data.get('appt_datetime') < earlist_appt_date.replace(
                    microsecond=0)
                    or (self.instance.visit_code != '2000'
                        and cleaned_data.get('appt_datetime') > latest_appt_date.replace(
                            microsecond=0))):
                    raise forms.ValidationError(
                        'The appointment datetime cannot be outside the window period, '
                        'please correct. See earliest, ideal and latest datetimes below.')

    def validate_appt_new_or_complete(self):
        """
        Validates the caregiver appointment model by overriding existing appointment
        validation functions.
        """
        pass

    class Meta:
        model = Appointment
        fields = '__all__'
