from rest_framework import serializers

from utils.serializers import DebateSerializerMixin, VenueSerializer


class EditDebateVenuesDebateSerializer(DebateSerializerMixin):
    """ Returns debates for the Edit Debate Teams view"""
    venue = serializers.PrimaryKeyRelatedField(read_only=True)  # Override


class EditDebateVenuesVenueSerializer(VenueSerializer):
    """ Returns venues for use in the allocate Debate Venues view """

    # TODO: fetch categories
    # TODO: fetch constraints
    class Meta:
        model = VenueSerializer.Meta.model
        fields = (*VenueSerializer.Meta.fields, 'priority') # Add fields
