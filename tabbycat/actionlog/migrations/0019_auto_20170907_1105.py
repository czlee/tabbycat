# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-09-07 11:05
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('actionlog', '0018_auto_20170812_0729'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='actionlogentry',
            options={'verbose_name': 'action log', 'verbose_name_plural': 'action log entries'},
        ),
        migrations.AlterField(
            model_name='actionlogentry',
            name='content_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.ContentType', verbose_name='content type'),
        ),
        migrations.AlterField(
            model_name='actionlogentry',
            name='ip_address',
            field=models.GenericIPAddressField(blank=True, null=True, verbose_name='IP address'),
        ),
        migrations.AlterField(
            model_name='actionlogentry',
            name='object_id',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='object ID'),
        ),
        migrations.AlterField(
            model_name='actionlogentry',
            name='round',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tournaments.Round', verbose_name='round'),
        ),
        migrations.AlterField(
            model_name='actionlogentry',
            name='timestamp',
            field=models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='timestamp'),
        ),
        migrations.AlterField(
            model_name='actionlogentry',
            name='tournament',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tournaments.Tournament', verbose_name='tournament'),
        ),
        migrations.AlterField(
            model_name='actionlogentry',
            name='type',
            field=models.CharField(choices=[('ba.disc', 'Discarded ballot set'), ('ba.ckin', 'Checked in ballot set'), ('ba.crea', 'Created ballot set'), ('ba.edit', 'Edited ballot set'), ('ba.conf', 'Confirmed ballot set'), ('ba.subm', 'Submitted ballot set from the public form'), ('fb.subm', 'Submitted feedback from the public form'), ('fb.save', 'Saved feedback'), ('ts.edit', 'Edited adjudicator test score'), ('aj.note', 'Set adjudicator note'), ('aa.save', 'Saved adjudicator allocation'), ('aa.auto', 'Auto-allocated adjudicators'), ('ve.save', 'Saved a venue manual edit'), ('ve.auto', 'Auto-allocated venues'), ('ve.ca.edit', 'Edited venue categories'), ('dr.crea', 'Created draw'), ('dr.conf', 'Confirmed draw'), ('dr.rege', 'Regenerated draw'), ('dr.rele', 'Released draw'), ('dr.unre', 'Unreleased draw'), ('mu.save', 'Saved a matchup manual edit'), ('dv.save', 'Saved divisions'), ('mo.edit', 'Added/edited motion'), ('mo.rele', 'Released motions'), ('mo.unre', 'Unreleased motions'), ('db.im.edit', 'Edited debate importance'), ('br.aj.set', 'Changed adjudicator breaking status'), ('br.el.edit', 'Edited break eligibility'), ('br.ca.edit', 'Edited break categories'), ('br.gene', 'Generated the team break for all categories'), ('br.upda', 'Edited breaking team remarks and updated all team breaks'), ('br.upd1', 'Edited breaking team remarks and updated this team break'), ('br.rm.edit', 'Edited breaking team remarks'), ('rd.st.set', 'Set start time'), ('rd.adva', 'Advanced the current round to'), ('av.tm.save', 'Edited teams availability'), ('av.aj.save', 'Edited adjudicators availability'), ('av.ve.save', 'Edited venue availability'), ('op.edit', 'Edited tournament options'), ('se.edit', 'Edited speaker category eligibility'), ('se.ca.edit', 'Edited speaker categories')], max_length=10, verbose_name='type'),
        ),
        migrations.AlterField(
            model_name='actionlogentry',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='user'),
        ),
    ]
