<template>
  <div class="analyse">
    <table class="table is-bordered">
      <tbody>
        <tr v-for="sent in sentencesWithDate">
          <td @click="log(sent)"><a>{{sent.text}}</a></td>
          <!-- captionEnts -->
          <td>
            <table class="table is-bordered">
              <tr v-for="ent in sent.captionEnts">
                <td>{{ent}}</td>
              </tr>
            </table>
          </td>
          <!-- events -->
          <td>
            <table class="table is-bordered">
              <tr v-for="event in sent.events">
                <td>{{event.date}} << {{event.text}}</td>
                <td>
                  <!-- <table class="table">
                    <tr v-for="(w,i) in event.wiki" v-if="event.scores[i] > 0">
                      <td>{{w.text}}</td>
                      <td>{{parseInt(event.scores[i] * 100)}}</td>
                    </tr>
                  </table> -->
                  <!-- {{event.wiki.length}} -->
                  <table v-if="event.wiki" class="table">
                    <tr v-for="(w,i) in event.wiki" v-if="event.scores[i].filter(s => s).length">
                      <td @click="log(w.ents)">{{w.text}}</td>
                      <td>{{ event.scores[i].map(s => parseInt(s*100)).join(',') }}</td>
                    </tr>
                  </table>
                </td>
                <td>
                  <div v-if="event.match" @click="log(event.match)">
                    <a><strong>MATCH FOUND:</strong> {{event.match.text}}</a>
                  </div>
                  <div v-else>no match</div>
                </td>
                <td>
                  <table class="table is-bordered">
                    <tr v-for="ent in event.ents.item">
                      <td>{{ent}}</td>
                    </tr>
                  </table>
                </td>
                <td>
                  <table class="table is-bordered">
                    <tr v-for="ent in event.ents.before">
                      <td>{{ent}}</td>
                    </tr>
                  </table>
                </td>
                <td>
                  <table class="table is-bordered">
                    <tr v-for="ent in event.ents.after">
                      <td>{{ent}}</td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>

export default {
  data() {
    return {
      matchData: this.$store.matchData,
      matchIndex: 2
    }
  },
  computed: {
    videoData() {
      return this.matchData[this.matchIndex];
    },
    sentences() {
      return this.videoData.captions.sents.map((sent, i) => {
        return {
          text: sent,
          captionEnts: this.videoData.captions.ents[i],
          heidelSents: this.videoData.heidel.sents[i],
          events: this.videoData.events[i],
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
    }
  },
  methods: {
    log(item) {
      console.log(item);
    }
  }
}
</script>

<style lang="scss" scoped>
.analyse {
  font-size: 10px;
}
</style>
