# Order state contract

Guest checkout creates an order and provisional customer-facing invoice representation. The owner may review and edit it before confirmation. Customers may request cancellation but cannot cancel directly; the owner approves or rejects the request. The owner sets the estimated delivery date after confirmation. Tawzeevo exposes no customer-facing delivery tracking.

The exact state machine is a Phase 5 gate and is not invented here.
