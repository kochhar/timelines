function requireAll(ctx) {
    return ctx.keys().map(ctx)
}

// import all the match-*.json files.
const matchDataRequire = require.context('../data', true, /match-.*\.json$/)
const matchData = requireAll(matchDataRequire)

export default {
    matchData
}
