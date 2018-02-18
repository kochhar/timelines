import json

def article_url_from_event(event):
    return event.get('article')

def get_wikipedia_urls(extract):
    urls = []
    for event in extract['events']:
        for candidate in event:
            match = candidate.get('match')
            if not match: continue

            wptopic_sel = match.get('wptopic_sel')
            if not wptopic_sel: continue
            urls.append(article_url_from_event(wptopic_sel))

            part_of = wptopic_sel.get('part_of_arr', [])
            for part_of_event in part_of:
                urls.append(article_url_from_event(part_of_event))

            wptopic_rel = match.get('wptopic_rel', [])
            part_of_sets = wptopic_rel.get('part_of', [])
            for sib_event_set in part_of_sets:
                for sib_event in sib_event_set:
                    urls.append(article_url_from_event(sib_event))

    return urls

if __name__ == '__main__':
    extract = json.loads(''.join(open('wikidata_extract.json').readlines()))
    url_set = set(url for url in get_wikipedia_urls(extract) if url)

    for url in url_set:
        print(url)

