#ifndef GATEWAY_EXCEPTION_H
#define GATEWAY_EXCEPTION_H

typedef struct {
    int error_code;
    char message[256];
} GatewayError;

#endif
