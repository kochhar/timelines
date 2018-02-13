import * as handlers from './handlers'
import Joi from 'joi'

export default [
  {
      method: 'GET',
      path:'/hello', 
      handler: handlers.startDownstream,
      config: {
        validate: {
          // query: {
          //   wbId: Joi.string().required()
          // }
        }
      }
  }
]