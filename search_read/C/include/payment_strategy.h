#ifndef PAYMENT_STRATEGY_H
#define PAYMENT_STRATEGY_H

#include "payment_types.h"
#include "gateway_exception.h"

typedef struct PaymentStrategy {
    const char* name;
    int (*pay)(const PaymentRequest* request, GatewayError* error);
} PaymentStrategy;

#endif
