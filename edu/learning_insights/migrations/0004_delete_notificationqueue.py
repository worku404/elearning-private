from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("learning_insights", "0003_notificationpreference_telegram_critical_alerts_enabled_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="NotificationQueue",
        ),
    ]

