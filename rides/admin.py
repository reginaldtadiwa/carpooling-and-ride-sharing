from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import RideRequest, Pool, PoolMembership, Driver, Trip

admin.site.site_header = "Carpooling Administration"
admin.site.site_title = "Carpooling Admin Portal"
admin.site.index_title = "Welcome to Carpooling Admin Portal"
# Resources for export functionality
class RideRequestResource(resources.ModelResource):
    class Meta:
        model = RideRequest
        fields = ('id', 'rider__username', 'pickup_address', 'destination_address', 
                 'status', 'fare_estimate', 'created_at', 'updated_at')
        export_order = fields

class PoolResource(resources.ModelResource):
    class Meta:
        model = Pool
        fields = ('id', 'status', 'max_riders', 'max_wait_time', 
                 'created_at', 'closed_at', 'estimated_fare')
        export_order = fields

class PoolMembershipResource(resources.ModelResource):
    class Meta:
        model = PoolMembership
        fields = ('id', 'pool__id', 'ride_request__id', 'pickup_order', 
                 'dropoff_order', 'joined_at')
        export_order = fields

class DriverResource(resources.ModelResource):
    class Meta:
        model = Driver
        fields = ('id', 'user__username', 'vehicle_type', 'license_plate', 
                 'max_capacity', 'is_available', 'current_latitude', 
                 'current_longitude', 'rating')
        export_order = fields

class TripResource(resources.ModelResource):
    class Meta:
        model = Trip
        fields = ('id', 'pool__id', 'driver__user__username', 'start_time', 
                 'end_time', 'actual_fare')
        export_order = fields

# Admin configurations
@admin.register(RideRequest)
class RideRequestAdmin(ImportExportModelAdmin):
    resource_class = RideRequestResource
    list_display = ('id', 'rider', 'pickup_address', 'destination_address', 
                   'status', 'fare_estimate', 'created_at')
    list_filter = ('status', 'created_at', 'updated_at')
    search_fields = ('rider__username', 'pickup_address', 'destination_address')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 20
    
    fieldsets = (
        ('Rider Information', {
            'fields': ('rider',)
        }),
        ('Pickup Details', {
            'fields': ('pickup_latitude', 'pickup_longitude', 'pickup_address')
        }),
        ('Destination Details', {
            'fields': ('destination_latitude', 'destination_longitude', 'destination_address')
        }),
        ('Ride Information', {
            'fields': ('status', 'fare_estimate', 'created_at', 'updated_at')
        }),
    )

@admin.register(Pool)
class PoolAdmin(ImportExportModelAdmin):
    resource_class = PoolResource
    list_display = ('id', 'status', 'max_riders', 'max_wait_time', 
                   'created_at', 'closed_at', 'estimated_fare')
    list_filter = ('status', 'created_at', 'closed_at')
    search_fields = ('id',)
    readonly_fields = ('created_at',)
    list_per_page = 20

@admin.register(PoolMembership)
class PoolMembershipAdmin(ImportExportModelAdmin):
    resource_class = PoolMembershipResource
    list_display = ('id', 'pool', 'ride_request', 'pickup_order', 
                   'dropoff_order', 'joined_at')
    list_filter = ('joined_at',)
    search_fields = ('pool__id', 'ride_request__id')
    readonly_fields = ('joined_at',)
    list_per_page = 20

@admin.register(Driver)
class DriverAdmin(ImportExportModelAdmin):
    resource_class = DriverResource
    list_display = ('user', 'vehicle_type', 'license_plate', 'max_capacity', 
                   'is_available', 'rating', 'current_latitude', 'current_longitude')
    list_filter = ('is_available', 'vehicle_type')
    search_fields = ('user__username', 'license_plate', 'vehicle_type')
    list_editable = ('is_available',)
    list_per_page = 20
    
    fieldsets = (
        ('Driver Information', {
            'fields': ('user', 'vehicle_type', 'license_plate')
        }),
        ('Availability & Capacity', {
            'fields': ('is_available', 'max_capacity', 'rating')
        }),
        ('Current Location', {
            'fields': ('current_latitude', 'current_longitude')
        }),
    )

@admin.register(Trip)
class TripAdmin(ImportExportModelAdmin):
    resource_class = TripResource
    list_display = ('id', 'pool', 'driver', 'start_time', 'end_time', 'actual_fare')
    list_filter = ('start_time', 'end_time')
    search_fields = ('pool__id', 'driver__user__username')
    readonly_fields = ('start_time', 'end_time')
    list_per_page = 20
