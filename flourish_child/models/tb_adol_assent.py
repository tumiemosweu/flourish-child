from edc_action_item.model_mixins import ActionModelMixin

from django.apps import apps as django_apps
from django.db import models
from django_crypto_fields.fields import IdentityField
from edc_base.model_managers import HistoricalRecords
from edc_base.model_mixins import BaseUuidModel
from edc_base.model_validators import datetime_not_future
from edc_base.sites.site_model_mixin import SiteModelMixin
from edc_base.utils import age, get_utcnow
from edc_consent.field_mixins import (
    CitizenFieldsMixin, VulnerabilityFieldsMixin, ReviewFieldsMixin,
    VerificationFieldsMixin)
from edc_consent.field_mixins import IdentityFieldsMixin, PersonalFieldsMixin
from edc_consent.validators import eligible_if_yes
from edc_constants.choices import YES_NO
from edc_identifier.model_mixins import NonUniqueSubjectIdentifierFieldMixin
from edc_protocol.validators import datetime_not_before_study_start
from edc_search.model_mixins import SearchSlugManager

from ..action_items import CHILDASSENT_ACTION
from ..choices import IDENTITY_TYPE
from .eligibility import AssentEligibility
from .model_mixins import SearchSlugModelMixin


class ChildAssentManager(SearchSlugManager, models.Manager):

    def get_by_natural_key(self, subject_identifier):
        return self.get(
            subject_identifier=subject_identifier)


class TbAdolAssent(SiteModelMixin, NonUniqueSubjectIdentifierFieldMixin,
                   IdentityFieldsMixin, PersonalFieldsMixin, ReviewFieldsMixin,
                   VulnerabilityFieldsMixin, CitizenFieldsMixin, SearchSlugModelMixin,
                   ActionModelMixin, VerificationFieldsMixin, BaseUuidModel):

    tracking_identifier_prefix = 'TA'

    action_name = CHILDASSENT_ACTION

    subject_identifier = models.CharField(
        verbose_name="Subject Identifier",
        max_length=50,
        null=True)

    screening_identifier = models.CharField(
        verbose_name='Screening identifier',
        max_length=50)

    identity = IdentityField(
        verbose_name='Identity number',
        null=True,
        blank=True)

    identity_type = models.CharField(
        verbose_name='What type of identity number is this?',
        max_length=25,
        choices=IDENTITY_TYPE,
        null=True,
        blank=True)

    confirm_identity = IdentityField(
        help_text='Retype the identity number',
        null=True,
        blank=True)

    tb_testing = models.CharField(
        max_length=3,
        verbose_name=('Are you willing to be tested for TB ?'),
        choices=YES_NO,
        help_text='If no, participant is not eligible.')

    samples_future_studies = models.CharField(
        verbose_name=('18.    Use of Samples in Future Research: Do you give us permission '
                      'to use your blood samples for future studies? '),
        max_length=3,
        choices=YES_NO,)

    consent_datetime = models.DateTimeField(
        verbose_name='Assent date and time',
        validators=[
            datetime_not_before_study_start,
            datetime_not_future])

    ineligibility = models.TextField(
        verbose_name="Reason not eligible",
        max_length=150,
        null=True,
        editable=False)

    is_eligible = models.BooleanField(
        default=False,
        editable=False)

    objects = ChildAssentManager()

    history = HistoricalRecords()

    def __str__(self):
        return f'{self.subject_identifier}'

    def natural_key(self):
        return self.subject_identifier

    @property
    def subject_consent_cls(self):
        return django_apps.get_model('flourish_caregiver.subjectconsent')

    @property
    def child_age(self):
        child_age = age(self.dob, get_utcnow())
        return child_age.years

    def save(self, *args, **kwargs):
        eligibility_criteria = AssentEligibility(
            self.remain_in_study, self.hiv_testing, self.preg_testing, self.child_age)
        self.is_eligible = eligibility_criteria.is_eligible
        self.ineligibility = eligibility_criteria.error_message
        # if self.is_eligible and not self.subject_identifier:
        #     self.subject_identifier = self.update_subject_identifier
        super().save(*args, **kwargs)

    class Meta:
        app_label = 'flourish_child'
        verbose_name = 'TB Adolescent Assent'
        unique_together = (('screening_identifier', 'subject_identifier'),
                           ('first_name', 'last_name', 'identity'),
                           ('first_name', 'dob', 'initials'))
