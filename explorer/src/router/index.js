import Vue from 'vue'
import Router from 'vue-router'
import Video from '@/views/Video'
import Analyse from '@/views/Analyse'

Vue.use(Router)

export default new Router({
  routes: [
    {
      path: '/',
      redirect: '/video'
    },
    {
      path: '/video',
      name: 'Video',
      component: Video
    },
    {
      path: '/analyse',
      component: Analyse
    }
  ]
})
