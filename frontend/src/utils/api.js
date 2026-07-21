//centeralized API setup

import axios from 'axios';
import qs from 'qs';

const api = axios.create({
    baseURL: '/api',
    withCredentials: true,
    paramsSerializer: params => qs.stringify(params, { arrayFormat: 'repeat' }),
})

export default api;