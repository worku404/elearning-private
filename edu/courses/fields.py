from typing import Any
from django.core.exceptions import ObjectDoesNotExist
from django.db import models


class OrderField(models.PositiveIntegerField):
    """
    Auto-fills an order/index number when the field is empty.

    If `for_fields` is given, numbering is grouped by those fields.
    Example:
    - for_fields=["course"]
    - Module(course=A) gets order 0,1,2...
    - Module(course=B) starts again at 0,1,2...
    """

    def __init__(self, for_fields=None, *args, **kwargs):
        # Fields used to scope ordering (grouping key), e.g. ["course"].
        self.for_fields = for_fields
        super().__init__(*args, **kwargs)

    def pre_save(self, model_instance: models.Model, add: bool) -> Any:
        # Current value of this field on the instance (usually "order").
        current_value = getattr(model_instance, self.attname)

        # If user already set the value manually, keep default Django behavior.
        if current_value is not None:
            return super().pre_save(model_instance, add)

        # Field is empty -> compute next order value automatically.
        try:
            # Start from all rows of the same model.
            qs = self.model.objects.all()

            if self.for_fields:
                # Build dynamic filter using the current instance values.
                # Example for for_fields=["course"]:
                # {"course": model_instance.course}
                query = {
                    field: getattr(model_instance, field)
                    for field in self.for_fields
                }
                qs = qs.filter(**query)

            # Pick the row with the greatest current order value.
            last_item = qs.latest(self.attname)

            # Next item should be last + 1.
            value = getattr(last_item, self.attname) + 1

        except ObjectDoesNotExist:
            # No previous row in this group -> first value is 0.
            value = 0

        # Save computed value back to model instance before DB write.
        setattr(model_instance, self.attname, value)
        return value
