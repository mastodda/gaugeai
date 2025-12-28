'use client'
import { useState } from 'react'

export default function Home() {
  const [image, setImage] = useState(null)
  const [description, setDescription] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    console.log('Image:', image)
    console.log('Description:', description)
    // We'll add AI generation here later
  }

  return (
    <main className="min-h-screen p-8">
      <h1 className="text-3xl font-bold mb-8">AI Focus Group Generator</h1>
      
      <form onSubmit={handleSubmit} className="max-w-2xl space-y-4">
        <div>
          <label className="block mb-2 font-semibold">Product Image</label>
          <input 
            type="file" 
            accept="image/*"
            onChange={(e) => setImage(e.target.files[0])}
            className="block w-full"
          />
        </div>

        <div>
          <label className="block mb-2 font-semibold">Product Description</label>
          <textarea 
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full p-2 border rounded"
            rows="4"
            placeholder="Describe your product..."
          />
        </div>

        <button 
          type="submit"
          className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700"
        >
          Generate Responses
        </button>
      </form>
    </main>
  )
}