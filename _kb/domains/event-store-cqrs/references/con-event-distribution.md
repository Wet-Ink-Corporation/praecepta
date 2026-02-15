# Cross-Application Event Distribution

## Overview

Applications communicate via the `eventsourcing` library's built-in `System` class. Events flow through notification logs stored in PostgreSQL.

## System of Applications

Define a system topology connecting applications:

```python
from eventsourcing.system import System, ProcessApplication
from eventsourcing.dispatch import singledispatchmethod

class TrickCounters(ProcessApplication[UUID]):
    """Counts tricks learned across all dogs."""

    @singledispatchmethod
    def policy(self, domain_event, processing_event):
        pass

    @policy.register
    def _(self, domain_event: TrickAdded, processing_event):
        counter = self._get_or_create_counter(domain_event.trick)
        counter.increment()
        processing_event.collect_events(counter)

    def get_count(self, trick: str) -> int:
        try:
            counter = self.repository.get(Counter.create_id(trick))
            return counter.count
        except AggregateNotFoundError:
            return 0

# System topology
system = System(pipes=[
    [DogSchoolApplication, TrickCounters],
])
```

## Running Modes

### Development (Synchronous)

```python
from eventsourcing.system import SingleThreadedRunner

runner = SingleThreadedRunner(system)
runner.start()

school = runner.get(DogSchoolApplication)
counters = runner.get(TrickCounters)

school.add_trick(dog_id, "roll over")
assert counters.get_count("roll over") == 1  # Immediate

runner.stop()
```

### Production (Concurrent)

```python
from eventsourcing.system import MultiThreadedRunner

runner = MultiThreadedRunner(system)
runner.start()

school = runner.get(DogSchoolApplication)
school.add_trick(dog_id, "roll over")

# Allow time for async processing
import time
time.sleep(0.01)

counters = runner.get(TrickCounters)
assert counters.get_count("roll over") == 1

runner.stop()
```

## Separate Process Projections

For materialised views running as separate processes:

```python
from eventsourcing.projection import ProjectionRunner

with ProjectionRunner(
    application_class=DogSchoolApplication,
    projection_class=MyProjection,
    view_class=MyMaterialisedView,
    env={"PERSISTENCE_MODULE": "eventsourcing.postgres"},
) as runner:
    signal.signal(signal.SIGINT, lambda *_: runner.stop())
    runner.run_forever()
```

## Key Points

- `System` defines application topology via pipes
- `SingleThreadedRunner` for development (synchronous)
- `MultiThreadedRunner` for production (concurrent)
- `ProjectionRunner` for separate-process projections
- Events flow through PostgreSQL notification logs

## Prerequisites

- [Domain Modeling](con-domain-modeling.md) - Event fundamentals

## Related

- [Neo4j Projections](con-neo4j-projection.md) - Graph materialised views
- [Deployment](ref-deployment.md) - Production configuration
