import datetime
import uuid

from django.apps import apps as django_apps
from django.db.models import ManyToManyField, ForeignKey, OneToOneField, ManyToOneRel
from django.db.models.fields.reverse_related import OneToOneRel
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from edc_constants.constants import NEG, POS, YES
import xlwt


class ExportActionMixin:

    def export_as_csv(self, request, queryset):

        response = HttpResponse(content_type='application/ms-excel')
        response['Content-Disposition'] = 'attachment; filename=%s.xls' % (
            self.get_export_filename())

        wb = xlwt.Workbook(encoding='utf-8', style_compression=2)
        ws = wb.add_sheet('%s')

        row_num = 0
        obj_count = 0
        self.inline_header = False

        font_style = xlwt.XFStyle()
        font_style.font.bold = True
        font_style.num_format_str = 'YYYY/MM/DD h:mm:ss'

        field_names = [field.name for field in self.get_model_fields]

        if queryset and self.is_non_crf(queryset[0]):
            field_names.insert(0, 'previous_study')
            field_names.insert(1, 'child_exposure_status')

        if queryset and getattr(queryset[0], 'child_visit', None):
            field_names.insert(0, 'subject_identifier')
            field_names.insert(1, 'new_maternal_study_subject_identifier')
            field_names.insert(2, 'old_study_maternal_identifier')
            field_names.insert(5, 'visit_code')

        for col_num in range(len(field_names)):
            ws.write(row_num, col_num, field_names[col_num], font_style)

        for obj in queryset:
            data = []

            # Add subject identifier and visit code
            if getattr(obj, 'child_visit', None):

                subject_identifier = obj.child_visit.subject_identifier
                screening_identifier = self.screening_identifier(
                    subject_identifier=subject_identifier[:-3])
                previous_study = self.previous_bhp_study(
                    screening_identifier=screening_identifier)
                study_maternal_identifier = self.study_maternal_identifier(
                    screening_identifier=screening_identifier)
                child_exposure_status = self.child_hiv_exposure(study_maternal_identifier,
                                                                subject_identifier)

                data.append(subject_identifier)
                data.append(subject_identifier[:-3])
                data.append(study_maternal_identifier)
                data.append(previous_study)
                data.append(child_exposure_status)
                data.append(obj.child_visit.visit_code)

            elif self.is_non_crf(obj):
                subject_identifier = getattr(obj, 'subject_identifier')
                screening_identifier = self.screening_identifier(
                    subject_identifier=subject_identifier[:-3])
                previous_study = self.previous_bhp_study(
                    screening_identifier=screening_identifier)
                study_maternal_identifier = self.study_maternal_identifier(
                    screening_identifier=screening_identifier)
                child_exposure_status = self.child_hiv_exposure(study_maternal_identifier,
                                                                subject_identifier)

                data.append(previous_study)
                data.append(child_exposure_status)

            inline_objs = []
            for field in self.get_model_fields:

                if isinstance(field, ManyToManyField):
                    key_manager = getattr(obj, field.name)
                    field_value = ', '.join([obj.name for obj in key_manager.all()])
                    data.append(field_value)
                    continue
                if isinstance(field, (ForeignKey, OneToOneField)):
                    field_value = getattr(obj, field.name)
                    data.append(field_value.id)
                    continue
                if isinstance(field, OneToOneRel):
                    continue
                if isinstance(field, ManyToOneRel):
                    key_manager = getattr(obj, f'{field.name}_set')
                    inline_objs = key_manager.all()
                field_value = getattr(obj, field.name, '')
                data.append(field_value)

            if inline_objs:
                # Update header
                inline_fields = inline_objs[0].__dict__
                inline_fields = self.inline_exclude(field_names=inline_fields)
                inline_fields = list(inline_fields.keys())

                if not self.inline_header:
                    self.update_headers_inline(
                        inline_fields=inline_fields, field_names=field_names,
                        ws=ws, row_num=0, font_style=font_style)

                for inline_obj in inline_objs:
                    inline_data = []
                    inline_data.extend(data)
                    for field in inline_fields:
                        field_value = getattr(inline_obj, field, '')
                        inline_data.append(field_value)
                    row_num += 1
                    self.write_rows(data=inline_data, row_num=row_num, ws=ws)
            else:
                row_num += 1
                self.write_rows(data=data, row_num=row_num, ws=ws)
            obj_count += 1
        wb.save(response)
        return response

    export_as_csv.short_description = _(
        'Export selected %(verbose_name_plural)s')

    actions = [export_as_csv]

    def write_rows(self, data=None, row_num=None, ws=None):
        for col_num in range(len(data)):
            if isinstance(data[col_num], uuid.UUID):
                ws.write(row_num, col_num, str(data[col_num]))
            elif isinstance(data[col_num], datetime.datetime):
                dt = data[col_num]
                if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
                    dt = timezone.make_naive(dt)
                ws.write(row_num, col_num, dt, xlwt.easyxf(num_format_str='YYYY/MM/DD h:mm:ss'))
            elif isinstance(data[col_num], datetime.date):
                ws.write(row_num, col_num, data[col_num], xlwt.easyxf(num_format_str='YYYY/MM/DD'))
            else:
                ws.write(row_num, col_num, data[col_num])

    def update_headers_inline(self, inline_fields=None, field_names=None,
                              ws=None, row_num=None, font_style=None):
        top_num = len(field_names)
        for col_num in range(len(inline_fields)):
            ws.write(row_num, top_num, inline_fields[col_num], font_style)
            top_num += 1
            self.inline_header = True

    def get_export_filename(self):
        date_str = datetime.datetime.now().strftime('%Y-%m-%d')
        filename = "%s-%s" % (self.model.__name__, date_str)
        return filename

    def screening_identifier(self, subject_identifier=None):
        """Returns a screening identifier.
        """
        consent_cls = django_apps.get_model('flourish_caregiver.subjectconsent')
        consent = consent_cls.objects.filter(subject_identifier=subject_identifier)
        if consent:
            return consent.last().screening_identifier
        return None

    def previous_bhp_study(self, screening_identifier=None):
        dataset_cls = django_apps.get_model('flourish_caregiver.maternaldataset')
        if screening_identifier:
            try:
                dataset_obj = dataset_cls.objects.get(
                    screening_identifier=screening_identifier)
            except dataset_cls.DoesNotExist:
                return None
            else:
                return dataset_obj.protocol

    def study_maternal_identifier(self, screening_identifier=None):
        dataset_cls = django_apps.get_model('flourish_caregiver.maternaldataset')
        if screening_identifier:
            try:
                dataset_obj = dataset_cls.objects.get(
                    screening_identifier=screening_identifier)
            except dataset_cls.DoesNotExist:
                return None
            else:
                return dataset_obj.study_maternal_identifier

    def child_hiv_exposure(self, study_maternal_identifier=None, subject_identifier=None):

        child_dataset_cls = django_apps.get_model('flourish_child.childdataset')

        if study_maternal_identifier:
            child_dataset_objs = child_dataset_cls.objects.filter(
                study_maternal_identifier=study_maternal_identifier)

            if child_dataset_objs:
                if child_dataset_objs[0].infant_hiv_exposed in ['Exposed', 'exposed']:
                    return 'HEU'
                elif child_dataset_objs[0].infant_hiv_exposed in ['Unexposed', 'unexposed']:
                    return 'HUU'
        else:
            rapid_test_cls = django_apps.get_model('flourish_caregiver.hivrapidtestcounseling')
            maternal_hiv_status = None

            try:
                rapid_test_obj = rapid_test_cls.objects.get(
                    maternal_visit__visit_code='1000M', maternal_visit__visit_code_sequence=0,
                    maternal_visit__subject_identifier=subject_identifier[:-3],
                    rapid_test_done=YES)
            except rapid_test_cls.DoesNotExist:
                antenatal_enrollment_cls = django_apps.get_model(
                    'flourish_caregiver.antenatalenrollment')
                try:
                    antenatal_enrollment = antenatal_enrollment_cls.objects.get(
                        subject_identifier=subject_identifier[:-3])
                except antenatal_enrollment_cls.DoesNotExist:
                    # To refactor to include new enrollees
                    maternal_hiv_status = 'UNK'
                else:
                    maternal_hiv_status = antenatal_enrollment.enrollment_hiv_status
            else:
                maternal_hiv_status = rapid_test_obj.result

            if maternal_hiv_status == POS:
                return 'HEU'
            elif maternal_hiv_status == NEG:
                return 'HUU'
            else:
                return 'UNK'

    def is_non_crf(self, obj):

        if getattr(obj, 'subject_identifier'):
            return True
        else:
            return False

    @property
    def get_model_fields(self):
        return self.model._meta.get_fields()

    def inline_exclude(self, field_names={}):
        exclude = ['_state', 'revision', 'hostname_modified', 'hostname_created',
                   'user_modified', 'user_created', 'device_created', 'device_modified']
        for field in exclude:
            del field_names[field]
        return field_names
