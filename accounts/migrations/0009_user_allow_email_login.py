from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0008_user_must_change_password_delete_recoveryrequest')]

    operations = [
        migrations.AddField(
            model_name='user',
            name='allow_email_login',
            field=models.BooleanField(default=False, verbose_name='Permitir ingresar con correo electrónico'),
        ),
    ]
