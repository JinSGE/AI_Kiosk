// utils/aiApiCaller.js
const axios = require('axios');
const fs = require('fs');
const FormData = require('form-data');
const path = require('path');

// AI API 호출 함수
async function callAiApi(input, inputType) {
  // AI 서비스 엔드포인트 설정
  const AI_API_BASE_URL = process.env.AI_API_URL || 'http://localhost:5000/api/v1';
  
  try {
    console.log(`AI API 호출 시작 - 타입: ${inputType}, 엔드포인트: ${AI_API_BASE_URL}`);
    let response;
    
    // 텍스트 입력 처리
    if (inputType === 'text') {
      console.log(`텍스트 API 호출: ${AI_API_BASE_URL}/kiosk/text-input, 내용: ${input}`);
      
      response = await axios.post(`${AI_API_BASE_URL}/kiosk/text-input`, {
        text: input
      }, {
        timeout: 30000
      });
      
      console.log('텍스트 API 응답 수신:', response.status);
      const responseData = response.data;
      
      let audioBase64 = null;
      const audioPath = responseData.audio_path;
      
      if (audioPath && fs.existsSync(audioPath)) {
        console.log(`오디오 파일 로드: ${audioPath}`);
        const audioBuffer = fs.readFileSync(audioPath);
        audioBase64 = `data:audio/wav;base64,${audioBuffer.toString('base64')}`;
      } else if (responseData.audio_base64) {
        audioBase64 = responseData.audio_base64;
      } else {
        console.log(`오디오 파일을 찾을 수 없음: ${audioPath}`);
      }
      
      return {
        input_text: input,
        response_text: responseData.response_text,
        audio_path: audioPath,
        audio_base64: audioBase64,
        current_state: responseData.current_state || 'unknown'
      };
    } 
    // 오디오 입력 처리
    else if (inputType === 'audio') {
      console.log(`오디오 API 호출 준비: ${AI_API_BASE_URL}/kiosk/process-audio`);
      const formData = new FormData();
      let tempFilePath = null;
      
      const audioDir = path.join(__dirname, '../audio_input');
      if (!fs.existsSync(audioDir)) {
        fs.mkdirSync(audioDir, { recursive: true });
      }
      
      if (typeof input === 'string' && fs.existsSync(input)) {
        console.log(`기존 오디오 파일 사용: ${input}`);
        formData.append('file', fs.createReadStream(input), path.basename(input));
      } else if (typeof input === 'string' && input.includes('base64')) {
        console.log('base64 데이터를 파일로 변환');
        const base64Data = input.split(',')[1] || input;
        const audioBuffer = Buffer.from(base64Data, 'base64');
        
        tempFilePath = path.join(audioDir, `temp_${Date.now()}.webm`);
        fs.writeFileSync(tempFilePath, audioBuffer);
        formData.append('file', fs.createReadStream(tempFilePath), path.basename(tempFilePath));
      } else if (Buffer.isBuffer(input)) {
        console.log('버퍼 데이터를 파일로 변환');
        tempFilePath = path.join(audioDir, `temp_${Date.now()}.webm`);
        fs.writeFileSync(tempFilePath, input);
        formData.append('file', fs.createReadStream(tempFilePath), path.basename(tempFilePath));
      } else {
        throw new Error('지원되지 않는 오디오 입력 형식입니다.');
      }
      
      console.log('오디오 API 호출 실행');
      
      response = await axios.post(
        `${AI_API_BASE_URL}/kiosk/process-audio`,
        formData,
        {
          headers: { ...formData.getHeaders() },
          timeout: 60000,
          maxContentLength: 20 * 1024 * 1024,
          maxBodyLength: 20 * 1024 * 1024
        }
      );
      
      console.log('오디오 API 응답 수신:', response.status);
      
      if (tempFilePath && fs.existsSync(tempFilePath)) {
        console.log(`임시 파일 삭제: ${tempFilePath}`);
        fs.unlinkSync(tempFilePath);
      }
      
      const responseData = response.data;
      let audioBase64 = null;
      const audioPath = responseData.audio_path;
      
      if (audioPath && fs.existsSync(audioPath)) {
        console.log(`오디오 파일 로드: ${audioPath}`);
        const audioBuffer = fs.readFileSync(audioPath);
        audioBase64 = `data:audio/wav;base64,${audioBuffer.toString('base64')}`;
      } else if (responseData.audio_base64) {
        audioBase64 = responseData.audio_base64;
      } else {
        console.log(`오디오 파일을 찾을 수 없음: ${audioPath}`);
      }
      
      return {
        input_text: responseData.input_text || "인식된 텍스트",
        response_text: responseData.response_text,
        audio_path: audioPath,
        audio_base64: audioBase64,
        current_state: responseData.current_state || 'unknown'
      };
    }
    
    throw new Error('지원하지 않는 입력 유형입니다.');
  } catch (error) {
    console.error('AI API 호출 오류:', error.message);
    if (error.response) {
      console.error('API 응답 오류 상태:', error.response.status);
      console.error('API 응답 오류 데이터:', error.response.data);
    } else if (error.request) {
      console.error('요청에 대한 응답 없음 (서버 연결 실패)');
    }
    
    return {
      input_text: inputType === 'text' ? input : "인식 실패",
      response_text: "죄송합니다. 요청을 처리하는 중에 문제가 발생했습니다. 다시 시도해 주세요.",
      audio_path: null,
      audio_base64: null,
      current_state: 'error'
    };
  }
}

module.exports = { callAiApi };
