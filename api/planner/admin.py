from django import forms
from django.contrib import admin, messages

from .importers import import_prices, read_price_rows
from .models import City, PriceList, Station


class PriceUploadForm(forms.ModelForm):
    file = forms.FileField(help_text="OPIS CSV, same columns as the sample file.")

    class Meta:
        model = PriceList
        fields = ["country", "source", "as_of"]

    def clean_file(self):
        upload = self.cleaned_data["file"]
        try:
            read_price_rows(upload)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
        upload.seek(0)
        return upload


@admin.register(PriceList)
class PriceListAdmin(admin.ModelAdmin):
    list_display = ["source", "as_of", "country", "active", "uploaded_at"]
    list_filter = ["country", "active"]

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = PriceUploadForm
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        if obj is None:
            return ["country", "source", "as_of", "file"]
        return ["country", "source", "as_of", "active"]

    def get_readonly_fields(self, request, obj=None):
        return ["country", "source", "as_of"] if obj else []

    def save_model(self, request, obj, form, change):
        if change:
            return super().save_model(request, obj, form, change)
        report = import_prices(form.cleaned_data["file"], obj.country, obj.source, obj.as_of)
        # The importer created the row; point the admin at it instead of saving a second one.
        obj.pk = report.price_list.pk
        obj.uploaded_at = report.price_list.uploaded_at
        obj.active = True
        obj._state.adding = False
        messages.info(request, report.summary())
        if report.skipped_unknown_city:
            messages.warning(request, "No city for: " + "; ".join(report.skipped_unknown_city[:30]))


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(City)
class CityAdmin(ReadOnlyAdmin):
    list_display = ["name", "state", "population", "lat", "lng"]
    search_fields = ["name", "state"]


@admin.register(Station)
class StationAdmin(ReadOnlyAdmin):
    list_display = ["opis_id", "name", "address", "city"]
    search_fields = ["opis_id", "name", "city__name"]
    list_select_related = ["city"]
