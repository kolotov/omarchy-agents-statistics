function dateKey(date) {
    return date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0") + "-" + String(date.getDate()).padStart(2, "0")
}

function calendar(today) {
    var end = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 12)
    var first = new Date(end.getFullYear() - 1, end.getMonth(), end.getDate() + 1, 12)
    var start = new Date(first)
    start.setDate(start.getDate() - start.getDay())
    var cells = []
    for (var cursor = new Date(start); cursor <= end || cursor.getDay() !== 0; cursor.setDate(cursor.getDate() + 1)) {
        cells.push({ date: dateKey(cursor), month: cursor.getMonth(), day: cursor.getDate(), valid: cursor >= first && cursor <= end })
    }
    return cells
}

function validate(value) {
    if (!value || value.schemaVersion !== 1 || !value.days || Array.isArray(value.days)) throw new Error("Invalid snapshot")
    var numeric = ["totalTokens", "totalPrompts", "agentSeconds", "totalSessions", "activeDays", "currentStreak", "longestStreak", "peakTokens", "accounts", "files", "partialFiles"]
    var result = { days: {} }
    for (var i = 0; i < numeric.length; i++) {
        var key = numeric[i], n = value[key]
        if (typeof n !== "number" || !isFinite(n) || n < 0 || n > 9e15) throw new Error("Invalid counter")
        result[key] = n
    }
    var keys = Object.keys(value.days)
    if (keys.length > 20000) throw new Error("Too many days")
    for (var d = 0; d < keys.length; d++) {
        var day = keys[d], row = value.days[day]
        if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || !row) throw new Error("Invalid day")
        var clean = {}
        for (var f = 0; f < 3; f++) {
            var field = ["tokens", "prompts", "seconds"][f], number = row[field]
            if (typeof number !== "number" || !isFinite(number) || number < 0 || number > 9e15) throw new Error("Invalid day value")
            clean[field] = number
        }
        result.days[day] = clean
    }
    return result
}
