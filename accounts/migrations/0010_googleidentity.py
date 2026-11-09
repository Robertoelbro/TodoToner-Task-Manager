from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [('accounts', '0009_user_allow_email_login')]
    operations = [
        migrations.CreateModel(
            name='GoogleIdentity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(max_length=255, unique=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                    related_name='google_identity', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
