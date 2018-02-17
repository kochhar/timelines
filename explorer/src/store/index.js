function requireAll(ctx) {
    return ctx.keys().map(ctx)
}

// import all the match-*.json files.
const wikidataRequire = require.context('../data/wikidata', true, /wikidata_.*\.json$/)
const wikidatas = requireAll(wikidataRequire)

export default {
    wikidatas
}
