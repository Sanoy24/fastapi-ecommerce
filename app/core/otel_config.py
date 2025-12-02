# from opentelemetry import trace
# from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
# from opentelemetry.sdk.resources import Resource
# from opentelemetry.sdk.trace import TracerProvider
# from opentelemetry.sdk.trace.export import BatchSpanProcessor


# def setup_otel():
#     provider = TracerProvider(
#         resource=Resource.create(
#             {
#                 "service.name": "fastapi-ecommerce",
#                 "service.version": "1.0.0",
#                 "deployment.environment": "development",
#             }
#         )
#     )
#     exporter = OTLPSpanExporter(endpoint="http://apm-server:8200/v1/traces")
#     provider.add_span_processor(BatchSpanProcessor(exporter))

#     trace.set_tracer_provider(provider)
