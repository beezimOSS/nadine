# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-17 19:59
from __future__ import unicode_literals
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta

from django.conf import settings
from django.db import migrations, models
from django.utils import timezone
import django.db.models.deletion


def forward(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    OldBill = apps.get_model("nadine", "OldBill")
    Transaction = apps.get_model("nadine", "Transaction")
    UserBill = apps.get_model("nadine", "UserBill")
    BillLineItem = apps.get_model("nadine", "BillLineItem")
    Payment = apps.get_model("nadine", "Payment")
    Resource = apps.get_model("nadine", "Resource")
    tz = timezone.get_current_timezone()
    print

    # Pull our Coworking Day Resource
    DAY = Resource.objects.filter(key="day").first()

    print("    Migrating Old Bills...")
    for o in OldBill.objects.all().order_by('bill_date'):
        # OldBill -> UserBill
        if o.paid_by:
            user = o.paid_by
        else:
            user = o.user
        start = o.bill_date
        end = start + relativedelta(months=1) - timedelta(days=1)
        bill = UserBill.objects.create(
            user = user,
            period_start = start,
            period_end = end,
            due_date =  o.bill_date,
        )
        if o.membership:
            bill.membership = o.membership.new_membership
        bill_date = datetime.combine(o.bill_date, datetime.min.time())
        bill.created_ts = timezone.make_aware(bill_date, tz)
        bill.save()

        # We'll create one line item for the membership
        BillLineItem.objects.create(
            bill = bill,
            description = "Coworking Membership",
            amount = o.amount,
            custom = True,
        )

        # Add all the dropins
        for day in o.dropins.all().order_by('visit_date'):
            BillLineItem.objects.create(
                bill = bill,
                description = "%s Coworking Day" % day.visit_date,
                resource = DAY,
                activity_id = day.id,
                amount = 0
            )
        # Add all our guest dropins
        for day in o.guest_dropins.all().order_by('visit_date'):
            BillLineItem.objects.create(
                bill = bill,
                description = "%s Guest Coworking Day (%s)" % (day.visit_date, day.user.username),
                resource = DAY,
                activity_id = day.id,
                amount = 0
            )

        # If there are any transactions on this bill
        # we are going to manually mark this as paid
        if o.transactions.count() > 0:
            bill.mark_paid = True
            bill.save()

        # Transactions -> Payments
        for t in o.transactions.all():
            p = Payment.objects.create(
                bill = bill,
                user = user,
                paid_amount = t.amount,
            )
            p.payment_date = t.transaction_date
            p.save()


            # Move transaction notes to bill comments
            if t.note:
                comment = ""
                if bill.comment:
                    comment = bill.comment
                comment += t.note
                bill.comment = comment
                bill.save()


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('nadine', '0028_new_membership'),
    ]

    operations = [
        # Create our new models
        migrations.CreateModel(
            name='BillLineItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=200)),
                ('amount', models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ('activity_id', models.IntegerField(default=0)),
                ('custom', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payment_date', models.DateTimeField(auto_now_add=True)),
                ('payment_service', models.CharField(blank=True, help_text=b'e.g., Stripe, Paypal, Dwolla, etc. May be empty', max_length=200, null=True)),
                ('payment_method', models.CharField(blank=True, help_text=b'e.g., Visa, cash, bank transfer', max_length=200, null=True)),
                ('paid_amount', models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ('transaction_id', models.CharField(blank=True, max_length=200, null=True)),
                ('last4', models.IntegerField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='UserBill',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_ts', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('period_start', models.DateField()),
                ('period_end', models.DateField()),
                ('due_date', models.DateField()),
                ('in_progress', models.BooleanField(default=False)),
                ('mark_paid', models.BooleanField(default=False)),
                ('comment', models.TextField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bills', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='payment',
            name='bill',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='nadine.UserBill'),
        ),
        migrations.AddField(
            model_name='payment',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='billlineitem',
            name='bill',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='line_items', to='nadine.UserBill'),
        ),
        migrations.AddField(
            model_name='userbill',
            name='membership',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='bills', to='nadine.Membership'),
        ),
        migrations.AddField(
            model_name='billlineitem',
            name='resource',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='nadine.Resource'),
        ),

        # Convert all the old bills to new ones
        migrations.RunPython(forward, reverse),

    ]
