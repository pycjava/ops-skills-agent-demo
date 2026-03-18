# Message Preprocess Policy Design

**Goal:** Introduce a lightweight orchestration layer that can enforce deterministic preprocessing rules before an agent turn starts.

## Problem

The current chat flow stores image attachments and sends them with the next message, but the routing decision still depends on prompt compliance. That makes "image message must go through OCR first" a soft rule.

## Decision

Add a small message preprocess policy layer in the backend orchestration path.

- A policy inspects the current turn input and attachments.
- If no policy matches, the existing agent execution flow remains unchanged.
- If the current turn includes image attachments, the backend must run OCR first.
- OCR output is then injected into the downstream analysis message.
- The downstream stage must not receive raw image blocks again for the same turn.

## Scope

- WebSocket chat path is the primary target.
- The implementation should be extensible enough to support future preprocessors such as PDF extraction or CSV structuring.
- OCR preprocessing applies only to the current turn's image attachments, not every historical image in the conversation.

## Flow

1. User sends a message with attachment ids.
2. Backend builds the current-turn attachment snapshot.
3. Preprocess policy layer evaluates the turn.
4. If image attachments are present:
   - verify OCR availability
   - run OCR against current-turn images only
   - emit OCR progress/result events
   - save OCR result artifact
   - send OCR text into the downstream analysis stage
5. Run the downstream agent:
   - `router` conversations escalate to `supervisor`
   - non-router conversations continue with their current agent

## Error Handling

- If OCR is unavailable, stop before analysis and emit a clear limitation error.
- If OCR returns empty text, continue with an explicit empty OCR result block rather than guessing image content.

## Testing

- Unit-test preprocess policy resolution.
- Unit-test orchestration order: OCR stage before downstream stage.
- Unit-test current-turn attachment scoping for image blocks/context.
- Targeted WebSocket helper coverage for persisted OCR result events.
