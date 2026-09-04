# THASHU

## Intelligent Self-Reliant Robot

Thashu is an experimental intelligent robotics platform designed to combine **autonomous robot control, onboard computing, computer vision, speech interaction, local AI, mobile control, and future cloud AI capabilities** into a single integrated system.

The project is being developed collaboratively by **Tharun, Niteshvar, and Vishal Raj**.

---

## Project Vision

Thashu is intended to become a self-reliant intelligent robot capable of:

* Controlling its motors and hardware safely
* Receiving commands through a mobile application
* Processing information locally on the Raspberry Pi
* Using computer vision for environmental perception
* Using speech recognition and speech synthesis
* Running local AI capabilities
* Connecting to cloud AI when appropriate
* Maintaining reliable communication between hardware and software subsystems
* Operating as one coordinated robotic system rather than a collection of independent programs

The architecture is being developed incrementally. Features are added only when their underlying interfaces and dependencies are sufficiently stable.

---

## High-Level Architecture

```text
                         THASHU
                           │
             ┌─────────────┴─────────────┐
             │                           │
        Raspberry Pi                  ESP32
        Main Computer              Hardware Control
             │                           │
     ┌───────┼────────┐             ┌────┼────┐
     │       │        │             │    │    │
    AI      CV     Speech        Motors Sensors OLED
     │       │        │
     └───────┼────────┘
             │
       Robot Services
             │
        Communication
             │
             ▼
       Flutter Mobile App
             │
             ▼
          User
```

This diagram represents the conceptual system. The detailed architecture and communication contracts are maintained in `docs/`.

---

## Main Components

### ESP32 Firmware

Responsible for low-level and time-critical hardware control.

Typical responsibilities include:

* Motor control
* Sensor interfacing
* OLED/display control
* Hardware state management
* Receiving validated commands
* Reporting hardware telemetry
* Enforcing hardware-level safety constraints

The ESP32 should **not** become responsible for high-level AI or application logic.

---

### Raspberry Pi

Acts as the robot's primary onboard computing platform.

Expected responsibilities include:

* High-level robot logic
* Local AI
* Computer vision
* Speech recognition
* Text-to-speech
* Robot services
* Communication coordination
* Data processing
* Integration between the mobile application and hardware

---

### Flutter Mobile Application

Provides the human-facing control and monitoring interface.

Expected responsibilities include:

* Robot connection
* Manual controls
* Robot status
* Telemetry
* Configuration
* User interaction
* Future AI-related controls

The mobile application communicates with the robot through defined interfaces rather than directly manipulating low-level hardware.

---

### API / Communication Layer

Defines how the different Thashu subsystems communicate.

This layer is critical to integration.

Interfaces should define:

* Message formats
* Commands
* Responses
* Telemetry
* Error states
* Authentication/security requirements where applicable
* Connection states
* Version compatibility

**Interfaces are contracts.**

A subsystem should not arbitrarily change a shared interface without coordinating with the other subsystem owners.

---

## Repository Structure

```text
THASHU/
│
├── firmware/
│   └── esp32/
│
├── robot/
│   └── raspberry_pi/
│
├── mobile/
│   └── flutter/
│
├── api/
│
├── docs/
│   ├── architecture/
│   ├── protocols/
│   ├── hardware/
│   ├── decisions/
│   └── development/
│
├── tests/
│
├── .github/
│   └── workflows/
│
└── README.md
```

The exact directory structure may evolve as the implementation progresses, but architectural changes must be agreed upon before restructuring shared components.

---

# Team Development

Thashu is developed by three people working in parallel:

* **Tharun**
* **Niteshvar**
* **Vishal Raj**

The repository is the **single source of truth** for the project.

Do not maintain separate unofficial copies of the project as the primary development source.

---

## Development Rule

### `main` must remain stable.

Nobody should directly develop experimental features on `main`.

Use a feature branch:

```text
main
 │
 ├── feature/...
 ├── firmware/...
 ├── mobile/...
 └── integration/...
```

Changes should be:

```text
Branch
   ↓
Commit
   ↓
Push
   ↓
Pull Request
   ↓
Review
   ↓
Tests
   ↓
Merge
   ↓
main
```

This allows the team to work independently without turning integration into a final-stage problem.

---

## Branch Naming

Use descriptive branch names.

Examples:

```text
feature/esp32-motor-control
feature/mobile-robot-status
feature/pi-vision-service
feature/api-telemetry
fix/esp32-command-parser
fix/mobile-connection
docs/system-architecture
```

Avoid branches such as:

```text
test
new
final
final2
working
tharun-code
my-code
```

The branch name should describe **what is being changed**, not who created it.

---

# Integration Rules

Thashu contains tightly coupled hardware and software components.

Therefore:

### 1. Do not silently change shared interfaces.

If changing an API, protocol, message format, hardware pin mapping, or shared data structure affects another subsystem, coordinate the change first.

### 2. Keep changes small.

A small pull request is easier to review, test, merge, and debug.

### 3. Pull the latest `main` before starting major work.

This reduces integration drift.

### 4. Test before opening a pull request.

Do not use the team as the first testing environment.

### 5. Update documentation when an interface changes.

Code and its required documentation should evolve together.

### 6. Never commit secrets.

Do not commit:

* API keys
* passwords
* private tokens
* credentials
* private certificates
* personal access tokens

Use environment variables or an appropriate secrets mechanism.

---

# Pull Requests

Every significant change should be submitted through a Pull Request.

A PR should explain:

```text
What changed?
Why was it changed?
What files/components were affected?
How was it tested?
Does another subsystem need to change?
```

Before merging, verify:

* Build succeeds
* Relevant tests pass
* No unrelated changes are included
* Documentation is updated where necessary
* Shared interfaces remain compatible
* At least one teammate has reviewed the change

---

# Communication Between Subsystems

The most important integration principle in Thashu is:

> **Components communicate through defined contracts, not assumptions.**

For example:

```text
Flutter
   │
   │ defined protocol
   ▼
Raspberry Pi
   │
   │ defined protocol
   ▼
ESP32
   │
   ▼
Hardware
```

If one developer changes a message from:

```json
{
  "command": "forward"
}
```

to:

```json
{
  "action": "move_forward"
}
```

without updating the other side, the system can break even though both individual programs still compile.

Therefore, protocol changes must be treated as integration changes.

---

# Documentation

Important project knowledge belongs inside the repository.

Documentation should cover:

```text
docs/
├── architecture/
│   └── system-architecture.md
│
├── protocols/
│   ├── communication-protocol.md
│   └── message-format.md
│
├── hardware/
│   ├── wiring.md
│   ├── components.md
│   └── pinout.md
│
├── decisions/
│   └── architecture-decisions.md
│
└── development/
    ├── setup.md
    └── workflow.md
```

The README provides the overview.

Detailed engineering information belongs in `docs/`.

---

# Testing Strategy

Testing should happen at multiple levels.

```text
Unit Tests
    ↓
Component Tests
    ↓
Interface Tests
    ↓
Integration Tests
    ↓
Robot Hardware Tests
    ↓
Full-System Tests
```

Software that works independently is **not automatically integrated software**.

A successful Thashu build must eventually verify that:

```text
Mobile App
     ↓
Raspberry Pi
     ↓
ESP32
     ↓
Motor / Sensor Hardware
```

works together correctly.

---

# Continuous Integration

Automated checks should eventually run through GitHub Actions.

The CI system should progressively verify:

* Code formatting
* Static analysis
* Unit tests
* Builds
* Interface compatibility
* Integration tests where practical

The goal is to detect integration problems **when changes are introduced**, rather than discovering them after weeks of independent development.

---

# Hardware and Software Coordination

Hardware changes can affect software.

Examples include:

* ESP32 pin changes
* Sensor changes
* Motor driver changes
* Power architecture changes
* Communication interface changes
* Display changes
* Component substitutions

Therefore, hardware changes must be documented and communicated before dependent software is updated.

Hardware documentation should remain synchronized with the actual robot.

---

# Source of Truth

For project decisions, the following priority applies:

```text
Approved Architecture / Decisions
              ↓
          Repository
              ↓
       Current Implementation
              ↓
       Individual Workspaces
```

Personal notes, AI conversations, screenshots, and messages are **not authoritative project specifications** unless the relevant decision has been transferred into the repository.

---

# AI-Assisted Development

AI tools may be used by individual team members to:

* Understand code
* Generate implementation drafts
* Debug problems
* Write tests
* Improve documentation
* Research technical approaches

However:

> **AI-generated code is not automatically approved Thashu architecture.**

AI assistants must follow the existing project architecture and repository documentation.

They must not independently invent or replace project-wide architecture.

Any architectural change must be reviewed by the team.

---

# Current Development Status

Thashu is under active development.

Major system areas include:

* [ ] ESP32 firmware
* [ ] Raspberry Pi software
* [ ] Flutter mobile application
* [ ] Robot ↔ mobile communication
* [ ] Raspberry Pi ↔ ESP32 communication
* [ ] Motor control
* [ ] Sensor integration
* [ ] OLED interface
* [ ] Computer vision
* [ ] Speech recognition
* [ ] Text-to-speech
* [ ] Local AI
* [ ] Cloud AI integration
* [ ] Automated testing
* [ ] CI pipeline
* [ ] Full-system integration

Individual component completion does **not** mean the overall robot is complete.

---

# Development Philosophy

Thashu follows several core principles:

1. **Integration before complexity**
2. **Clear interfaces before implementation**
3. **Small changes before large rewrites**
4. **Tested code before merged code**
5. **Documented decisions before architectural changes**
6. **Stable `main` before experimentation**
7. **One shared source of truth**
8. **Hardware and software must evolve together**

The objective is not simply to produce more code.

The objective is to produce a **reliable integrated robot**.

---

## Team

**Tharun**
Thashu Development Team

**Niteshvar**
Thashu Development Team

**Vishal Raj**
Thashu Development Team

---

## Project Status

**Active Development**

Thashu is an evolving robotics project. Architecture, interfaces, and implementation details may change as engineering requirements are validated through testing.

---

## License

License information will be added when the project licensing decision is finalized.
