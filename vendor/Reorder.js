// Row reordering helpers from Omarchy (MIT).
// Rows the pointer must travel past the held slot before the target moves.
var DRAG_HYSTERESIS = 0.6

// How many rows a drag of `offset` has passed, fractionally. Rows are not all
// one height - a row with people is a line taller - so each is measured by its
// own pitch in `pitches`; without them every row is `rowPitch`.
function rowsPassed(dragIndex, offset, rowPitch, pitches) {
  if (!pitches) return offset / rowPitch
  var step = offset < 0 ? -1 : 1
  var left = Math.abs(offset)
  var passed = 0
  for (var i = dragIndex + step; i >= 0 && i < pitches.length; i += step) {
    var pitch = pitches[i] > 0 ? pitches[i] : rowPitch
    if (left < pitch) return step * (passed + left / pitch)
    left -= pitch
    passed++
  }
  return step * (passed + left / rowPitch)
}

// Where the dragged row lands when it drops into `target`: the pitches of the rows it passed.
function dropOffset(dragIndex, target, rowPitch, pitches) {
  var step = target < dragIndex ? -1 : 1
  var out = 0
  for (var i = dragIndex + step; step > 0 ? i <= target : i >= target; i += step)
    out += step * (pitches && pitches[i] > 0 ? pitches[i] : rowPitch)
  return out
}

function dragTargetFor(dragIndex, dragOffset, rowPitch, heldTarget, count, pitches) {
  if (dragIndex < 0 || rowPitch <= 0) return -1
  var raw = rowsPassed(dragIndex, dragOffset, rowPitch, pitches)
  var held = heldTarget < 0 ? 0 : heldTarget - dragIndex
  var next = Math.abs(raw - held) >= DRAG_HYSTERESIS ? Math.round(raw) : held
  return Math.max(0, Math.min(count - 1, dragIndex + next))
}

// The dragged row follows the pointer; rows it has passed step aside by one pitch.
function rowShift(index, dragIndex, dragTarget, dragOffset, rowPitch) {
  if (dragIndex < 0) return 0
  if (index === dragIndex) return dragOffset
  if (dragIndex < dragTarget && index > dragIndex && index <= dragTarget) return -rowPitch
  if (dragIndex > dragTarget && index >= dragTarget && index < dragIndex) return rowPitch
  return 0
}
