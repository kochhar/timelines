<template>
  <div class="timeline-simple">
    <table class="table is-bordered">
      <tbody>
        <tr v-for="sent in sentencesWithDate" :key="sent.sentInd" :class="{'focused': sent.sentInd == focusSentInd}">
          <td>
            {{sent.text}}
            <div class="buttons">
              <button class="button is-small" @click="log(sent)">Log</button>
              <button class="button is-small" @click="timestampChangeHandler(sent.timestamp)">Seek ({{timestampDisplay(sent.timestamp)}})</button>
            </div>
          </td>
          <td>
            <table class="table">
              <tbody>
                <tr v-for="event in sent.events" v-if="event.match">
                  <td>{{event.date}}</td>
                  <td>{{event.match.text}}</td>
                  <td>
                    <a :href="event.match.wptopic_sel.article" v-if="event.match.wptopic_sel">{{event.match.wptopic_sel.title.split('_').join(' ')}}</a>
                    <div v-else>no wikidata event</div>
                  </td>
                </tr/>
              </tbody>
            </table>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>

export default {
  props: {
    videoId: String,
    currTime: Number
  },
  data() {
    return {
    }
  },
  computed: {
    wikidata() {
      return this.$store.wikidatas.find(wd => wd.video_id == this.videoId);
    },
    sentences() {
      return this.wikidata.captions.sents.map((sent, i) => {
        return {
          sentInd: i,
          text: sent,
          timestamp: Number(this.wikidata.captions.timestamps[i]),
          captionEnts: this.wikidata.captions.ents[i],
          heidelSents: this.wikidata.heidel.sents[i],
          events: this.wikidata.events[i],
        }
      })
    },
    sentencesWithDate() {
      return this.sentences.filter(s => s.events && s.events.length);
    },
    sentencesWithWiki() {
      return this.sentencesWithDate.filter(s => s.events.filter(e => e.wiki.length).length)
    },
    sentencesWithMatch() {
      return this.sentencesWithWiki.filter(s => s.events.filter(e => e.match).length)
    },
    focusSentInd() {
      let sentAfter = this.sentences.find(s => s.timestamp > this.currTime);
      return sentAfter ? sentAfter.sentInd - 1 : -1;
    }
  },
  methods: {
    log(sent) {
      console.log('-------------')      
      console.log('SENTENCE:', sent.text);
      sent.events.forEach(e => {
        console.log('----')
        console.log('EVENT DATE:', e.date);
        console.log('WIKI BLURBS', e.wiki);
        console.log('WIKI MATCH', e.match);
        if(e.match) console.log('WIKIDATA EVENT', e.match.wptopic_sel);
      })
    },
    timestampDisplay(ts) {
      return `${parseInt(ts/60)}:${parseInt(ts%60)}`;
    },
    timestampChangeHandler(ts) {
      this.$emit('timestamp-change', ts);
    }
  } 
}
</script>

<style lang="scss" scoped>
tr.focused {
  background: rgba(255, 99, 71, 0.3);
}
</style>
