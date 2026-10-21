#include "include/event_listener.h"
#include "include/order_types.h"

int audit_on_event(const OrderEvent* event, EventError* error) {
    // Log the event details
    printf("Audit Event: Order ID = %llu, New Status = %d\n", event->order_id, event->new_status);
    return 0;
}