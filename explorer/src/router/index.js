import Vue from 'vue'
import Router from 'vue-router'
import Video from '@/views/Video'
import Analyse from '@/views/Analyse'
import AnalyseVideo from '@/views/AnalyseVideo'

Vue.use(Router)

export default new Router({
  routes: [
    {
      path: '/',
      redirect: '/analyse-video'
    },
    {
      path: '/video',
      name: 'Video',
      component: Video
    },
    {
      path: '/analyse',
      component: Analyse
    },
    {
      path: '/analyse-video',
      component: AnalyseVideo
    }
  ]
})
