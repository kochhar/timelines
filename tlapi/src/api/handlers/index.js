import wdk from 'wikidata-sdk'
import axios from 'axios'
import _ from 'lodash'

export let startDownstream = async (request, reply) => {
  let extract = request.query.extract;
  //filter Down to the matches
  //for each match - use wptopics to get wbids and enhance wp_topics
  //wp_sel - select one thats an event, if multiple make a guess
  //wp_rel - populate with topics related to wp_sel through category or part of
};

export let getStuff = async (request, reply) => {
  // given wikidataId - query wikidata get start-date, end-date, part-of, main-topic, instance-of - VS
  let wbIds = [request.query.wbId];

  let wptopics = await Promise.all(wbIds.map(wbId => getEntityInfo({wbId})));
  // console.log(wptopics.map(wpt => ({wpt.label, wpt.part_of_arr.length, wpt.event_category, wpt.start_time})));

  let wptopic_sel = wptopics.find(wpt => wpt.start_time);

  //add wptopic_sel.related
  let wptopic_rel = {};
  wptopic_rel.part_of = await Promise.all(wptopic_sel.part_of_arr.map(pot => getPoChildren({wbId: pot.event.value})));
  wptopic_rel.category = await getCategoryChildren({wbId: wptopic_sel.event_category.value});

  return {
    wptopics,
    wptopic_rel,
    wptopic_sel
  };

};

export let getEntityInfo = async ({wbId}) => {
  console.log('getting entity info for ', wbId);
  
  const sparql =`
  PREFIX schema: <http://schema.org/>
  SELECT ?item ?itemLabel ?article ?start_time ?end_time ?instance_of ?instance_ofLabel ?topic_s_main_category ?topic_s_main_categoryLabel WHERE {
    wd:${wbId} wdt:P361* ?item.
    OPTIONAL { ?item wdt:P580 ?start_time. }
    OPTIONAL { ?item wdt:P582 ?end_time. }
    OPTIONAL { ?item wdt:P31 ?instance_of. }
    OPTIONAL { ?item wdt:P910 ?topic_s_main_category. }
    OPTIONAL { 
      ?article schema:about ?item.
      ?article schema:inLanguage "en".
      ?article schema:isPartOf <https://en.wikipedia.org/>.   
    }
    SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
  }
  `;

  const entities = await sparqlEntities(sparql);

  //group by the wbId in questioj
  let rootEntity, part_of_arr = [];

  let entitiesById = _.groupBy(entities, 'event.value');
  Object.keys(entitiesById).forEach(currWbId => {
    let leaves = entitiesById[currWbId];
    let currEntity = {
      ...leaves[0],
      instance_of_arr: leaves.map(l => l.instance_of)
    };
    delete currEntity.instance_of;

    if (currWbId == wbId) rootEntity = currEntity;
    else part_of_arr.push(currEntity)

  });
  let ret = {
    ...rootEntity,
    part_of_arr
  };
  console.log(ret);
  return ret;
};

async function getPoChildren({wbId}) {
  //sparql query to fetch 
  const sparql = `
  PREFIX schema: <http://schema.org/>
  SELECT ?item ?itemLabel ?article ?start_time ?end_time ?main_subject ?main_subjectLabel WHERE {
    ?item wdt:P361 wd:${wbId}.
    OPTIONAL { ?item wdt:P580 ?start_time. }
    OPTIONAL { ?item wdt:P582 ?end_time. }
    OPTIONAL { ?item wdt:P910 ?main_subject. }
    OPTIONAL { 
      ?article schema:about ?item.
      ?article schema:inLanguage "en".
      ?article schema:isPartOf <https://en.wikipedia.org/>.   
    }
    SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
  }
  `;
  
  const entities = await sparqlEntities(sparql);
  return entities;
}

async function getCategoryChildren({wbId}) {
  //sparql query to fetch 
  const sparql = `
  SELECT ?category
        ?categoryLabel
        ?category_sib
        ?category_sibLabel
        WHERE {
   OPTIONAL { wd:${wbId} wdt:P910 ?category . }
   OPTIONAL { ?category_sib wdt:P910 ?category . }

   SERVICE wikibase:label {bd:serviceParam wikibase:language "en" . }
  }
  `;

  const entities = await sparqlEntities(sparql);
  return entities;
}

async function sparqlEntities(sparql) {
  const url = wdk.sparqlQuery(sparql);
  const resp = await axios(url);
  return cleanEntities(wdk.simplifySparqlResults(resp.data)) ;
}

function cleanEntities(entities) {
  entities.forEach(e => {
    e.event = e.item;
    delete e.item;
    e.event_category = e.topic_s_main_category;
    delete e.topic_s_main_category;
  });
  //filter down to events by checking start_time??
  //TO DO
  return entities;
}
